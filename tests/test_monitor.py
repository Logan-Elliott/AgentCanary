import os
import select
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agentcanary import Action, InotifyMonitor, MonitorError, Store, create_canary
from agentcanary.monitors import inotify


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    pytest.fail("bounded observation wait expired")


def setup(tmp_path):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    canary = create_canary(store, root, "token.env")
    return store, root, canary


def child_read(path):
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib,sys; pathlib.Path(sys.argv[1]).read_bytes()",
            str(path),
        ],
        check=True,
        timeout=5,
    )


def test_real_subprocess_read_without_self_access(tmp_path):
    store, root, canary = setup(tmp_path)
    with InotifyMonitor(store, root, run_id="kernel") as monitor:
        assert monitor.ready.is_set()
        assert monitor.watch_count == 1
        # Let startup notifications drain; validation must never become a READ.
        time.sleep(0.15)
        assert not store.events(action=Action.READ)
        child_read(canary.path)
        events = wait_for(lambda: store.events(action=Action.READ))
        assert all(event.pid is None and event.run_id == "kernel" for event in events)
        assert events[0].canary_id == canary.id
        assert events[0].provenance == "kernel_inode_access"
        assert not store.events(action=Action.COPY)
    assert not monitor.running
    assert monitor.watch_count == 0


@pytest.mark.parametrize("change", ["modify", "replace", "delete", "parent_move"])
def test_change_invalidates_coverage_and_never_rearms(tmp_path, change):
    store, root, canary = setup(tmp_path)
    target = Path(canary.path)
    with InotifyMonitor(store, root) as monitor:
        if change == "modify":
            target.write_text("no marker")
        elif change == "replace":
            replacement = root / "replacement"
            replacement.write_text("no marker")
            replacement.replace(target)
        elif change == "delete":
            target.unlink()
        else:
            root.rename(tmp_path / "moved")
        wait_for(lambda: monitor.watch_count == 0)
        if target.exists():
            child_read(target)
        assert not store.events(action=Action.READ)
        health = wait_for(
            lambda: [
                event
                for event in store.events(action=Action.MONITOR_HEALTH)
                if event.metadata["reason"] == "coverage_lost"
            ]
        )
        assert health[0].canary_id == canary.id


def test_snapshot_missing_altered_outside_and_empty(tmp_path):
    store, root, canary = setup(tmp_path)
    outside = create_canary(store, tmp_path / "other", "outside")
    missing = create_canary(store, root, "missing")
    Path(missing.path).unlink()
    Path(canary.path).write_text("altered")
    with InotifyMonitor(store, root) as monitor:
        assert monitor.watch_count == 0
        events = store.events(action=Action.MONITOR_HEALTH)
        reasons = {event.metadata["reason"] for event in events}
        assert {"outside_root", "missing_file", "altered_file", "snapshot_started"} <= reasons
        assert next(event for event in events if event.canary_id == outside.id).pid is None
        assert events[-1].metadata["healthy"] is False
    empty = Store(tmp_path / "empty-state")
    with InotifyMonitor(empty, root) as monitor:
        assert monitor.watch_count == 0
        assert empty.events()[-1].metadata["reason"] == "empty_registry"


def test_monitor_lifecycle_restart_refresh_and_no_descriptor_leak(tmp_path):
    store, root, canary = setup(tmp_path)
    before = len(os.listdir("/proc/self/fd"))
    monitor = InotifyMonitor(store, root)
    monitor.stop()
    monitor.start()
    with pytest.raises(MonitorError, match="already"):
        monitor.start()
    later = create_canary(store, root, "later")
    assert monitor.watch_count == 1
    monitor.stop()
    monitor.stop()
    monitor.start()
    assert monitor.watch_count == 2
    child_read(later.path)
    wait_for(lambda: store.events(action=Action.READ))
    monitor.stop()
    assert not monitor.running
    assert len(os.listdir("/proc/self/fd")) == before
    assert canary.id != later.id


def test_cli_readiness_and_sigterm(tmp_path):
    store, root, canary = setup(tmp_path)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentcanary",
            "--state-dir",
            str(tmp_path / "state"),
            "monitor",
            str(root),
            "--run-id",
            "cli",
            "--duration",
            "10",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert select.select([process.stdout], [], [], 5)[0], "CLI readiness timed out"
        line = process.stdout.readline()
        assert '"status": "ready"' in line
        child_read(canary.path)
        wait_for(lambda: store.events(action=Action.READ, run_id="cli"))
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert not stdout
        assert store.events()[-1].metadata["reason"] == "stopped"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def test_overflow_drops_all_coverage(tmp_path, monkeypatch):
    store, root, canary = setup(tmp_path)
    monitor = InotifyMonitor(store, root)
    original = inotify._Inotify.read
    injected = False

    def overflow(backend):
        nonlocal injected
        data = original(backend)
        if not injected:
            injected = True
            return data + struct.pack("iIII", -1, inotify.IN_Q_OVERFLOW, 0, 0)
        return data

    monkeypatch.setattr(inotify._Inotify, "read", overflow)
    with monitor:
        child_read(canary.path)
        wait_for(lambda: monitor.watch_count == 0)
        assert not store.events(action=Action.READ)
        wait_for(
            lambda: [
                event
                for event in store.events(action=Action.MONITOR_HEALTH)
                if event.metadata["reason"] == "queue_overflow"
            ]
        )


def test_start_failure_closes_descriptors(tmp_path, monkeypatch):
    store, root, _ = setup(tmp_path)
    before = len(os.listdir("/proc/self/fd"))

    def fail_add(*args):
        raise OSError("fixture watch failure")

    monkeypatch.setattr(inotify._Inotify, "add", fail_add)
    monitor = InotifyMonitor(store, root)
    with pytest.raises(MonitorError, match="startup"):
        monitor.start()
    assert not monitor.running
    assert monitor.watch_count == 0
    assert len(os.listdir("/proc/self/fd")) == before
    assert store.events()[-1].metadata["reason"] == "startup_failed"


def test_worker_sink_failure_is_visible_and_stops(tmp_path):
    store, root, canary = setup(tmp_path)

    class Sink:
        def record(self, event):
            if event.action == Action.READ:
                raise RuntimeError("fixture secret must not appear")
            return store.record(event)

    monitor = InotifyMonitor(store, root, sink=Sink())
    monitor.start()
    child_read(canary.path)
    wait_for(lambda: monitor.error)
    with pytest.raises(MonitorError, match="RuntimeError"):
        monitor.stop()
    assert not monitor.running
    assert "fixture secret" not in repr(store.events())
    assert store.events()[-1].metadata["reason"] == "worker_failed"


def test_invalid_root_and_platform_are_explicit(tmp_path, monkeypatch):
    store, root, _ = setup(tmp_path)
    with pytest.raises(MonitorError):
        InotifyMonitor(store, root / "absent").start()
    monkeypatch.setattr(inotify.sys, "platform", "win32")
    with pytest.raises(MonitorError):
        InotifyMonitor(store, root).start()
    assert store.events()[-1].metadata["reason"] == "startup_failed"
