import os
import select
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agentcanary import (
    Action,
    InotifyMonitor,
    MonitorError,
    Observer,
    Store,
    ToolInvocationError,
    create_canary,
)
from agentcanary.monitors import inotify


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("bounded integration wait expired")


def test_multiple_processes_and_artifacts_keep_both_provenances(tmp_path):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    canaries = [create_canary(store, root, f"fixture-{i}") for i in range(3)]
    code = (
        "import sys; from agentcanary import Store,Observer; "
        "observer=Observer(Store(sys.argv[1]),run_id=sys.argv[2]); "
        "[observer.read(path) for _ in range(8) for path in sys.argv[3:]]"
    )
    with InotifyMonitor(store, root, run_id="passive") as monitor:
        children = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    code,
                    str(tmp_path / "state"),
                    f"child-{i}",
                    *[canary.path for canary in canaries],
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            for i in range(2)
        ]
        try:
            for child in children:
                _, stderr = child.communicate(timeout=15)
                assert child.returncode == 0, stderr
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)
        wait_for(
            lambda: (
                {event.canary_id for event in store.events(action=Action.READ, run_id="passive")}
                == {canary.id for canary in canaries}
            )
        )
        reads = store.events(action=Action.READ)
        sdk = [event for event in reads if event.source == "sdk"]
        assert len(sdk) == 48
        assert {event.pid for event in sdk} == {child.pid for child in children}
        assert all(event.pid is None for event in reads if event.source == "inotify")
        assert len({event.seq for event in reads}) == len(reads)
        assert monitor.watch_count == 3
        monitor.check()


def test_concurrent_sdk_copies_never_overwrite(tmp_path):
    store = Store(tmp_path / "state")
    canary = create_canary(store, tmp_path / "workspace", "token")
    target = tmp_path / "copy"
    code = (
        "import sys; from agentcanary import Store,Observer; "
        "o=Observer(Store(sys.argv[1]));\n"
        "try: o.copy(sys.argv[2],sys.argv[3])\n"
        "except FileExistsError: sys.exit(3)\n"
    )
    children = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(tmp_path / "state"), canary.path, str(target)],
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    try:
        for child in children:
            child.communicate(timeout=10)
        assert sorted(child.returncode for child in children) == [0, 3]
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)
    events = store.events(action=Action.COPY)
    assert len(events) == 1
    assert events[0].pid in {child.pid for child in children}
    assert target.read_bytes() == Path(canary.path).read_bytes()


def test_mutation_between_validation_and_watch_is_not_accepted(tmp_path, monkeypatch):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    canary = create_canary(store, root, "token")
    original = inotify._Inotify.add

    def changed_add(backend, fd):
        Path(canary.path).write_text("changed during setup")
        return original(backend, fd)

    monkeypatch.setattr(inotify._Inotify, "add", changed_add)
    with InotifyMonitor(store, root) as monitor:
        assert monitor.watch_count == 0
        assert not store.events(action=Action.READ)
        assert any(
            event.metadata.get("reason") == "changed_during_start" for event in store.events()
        )


@pytest.mark.parametrize("failure", ["sink", "second_watch", "thread_start"])
def test_partial_start_failure_has_no_worker_or_descriptor_leak(tmp_path, monkeypatch, failure):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    for i in range(2):
        create_canary(store, root, f"fixture-{i}")
    before = len(os.listdir("/proc/self/fd"))

    class FailedSink:
        def record(self, event):
            raise RuntimeError("fixture private exception detail")

    monitor = InotifyMonitor(store, root, sink=FailedSink() if failure == "sink" else None)
    if failure == "second_watch":
        original = inotify._Inotify.add
        calls = 0

        def partial_add(backend, fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("fixture failed second watch")
            return original(backend, fd)

        monkeypatch.setattr(inotify._Inotify, "add", partial_add)
    elif failure == "thread_start":

        def failed_start(thread):
            raise RuntimeError("fixture failed thread start")

        monkeypatch.setattr(inotify.threading.Thread, "start", failed_start)
    with pytest.raises(MonitorError, match="startup"):
        monitor.start()
    assert not monitor.running
    assert monitor.watch_count == 0
    assert len(os.listdir("/proc/self/fd")) == before
    assert "private exception" not in str(monitor.error)


def test_malformed_kernel_buffer_is_visible(tmp_path, monkeypatch):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    canary = create_canary(store, root, "token")
    original = inotify._Inotify.read

    def malformed(backend):
        original(backend)
        return struct.pack("iIII", 1, inotify.IN_ACCESS, 0, 99)

    monkeypatch.setattr(inotify._Inotify, "read", malformed)
    monitor = InotifyMonitor(store, root)
    monitor.start()
    Path(canary.path).read_bytes()
    wait_for(lambda: monitor.error)
    with pytest.raises(MonitorError):
        monitor.stop()
    assert not monitor.running
    assert not store.events(action=Action.READ)
    assert store.events()[-1].metadata["reason"] == "worker_failed"


def test_sdk_copy_failure_rolls_back_and_symlink_parent_is_rejected(tmp_path, monkeypatch):
    store = Store(tmp_path / "state")
    canary = create_canary(store, tmp_path / "workspace", "token")
    observer = Observer(store)
    destination = tmp_path / "failed-copy"

    def fail_sync(fd):
        raise OSError("fixture disk failure")

    with monkeypatch.context() as scope:
        scope.setattr(os, "fsync", fail_sync)
        with pytest.raises(OSError):
            observer.copy(canary.path, destination)
    assert not destination.exists()
    assert not store.events(action=Action.COPY)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "workspace", target_is_directory=True)
    with pytest.raises(OSError):
        observer.copy(canary.path, link / "copy")


def test_tool_timeout_and_nonzero_exit_have_honest_input_evidence(tmp_path):
    store = Store(tmp_path / "state")
    canary = create_canary(store, tmp_path / "workspace", "token")
    observer = Observer(store)
    with pytest.raises(ToolInvocationError):
        observer.run_tool(
            [sys.executable, "-c", "import time; time.sleep(10)"], input=canary.token, timeout=0.05
        )
    result = observer.run_tool([sys.executable, "-c", "raise SystemExit(7)", canary.token])
    assert result.returncode == 7
    assert len(store.events(action=Action.TOOL_USE)) == 2
    assert all(
        event.metadata["operation"] == "invocation_attempt"
        for event in store.events(action=Action.TOOL_USE)
    )


@pytest.mark.parametrize("ending", ["duration", "sigint"])
def test_cli_duration_and_interrupt_shutdown(tmp_path, ending):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    create_canary(store, root, "token")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agentcanary",
            "--state-dir",
            str(tmp_path / "state"),
            "monitor",
            str(root),
            "--duration",
            "0.1" if ending == "duration" else "10",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([process.stdout], [], [], 5)[0]
        assert '"status": "ready"' in process.stdout.readline()
        if ending == "sigint":
            process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == (0 if ending == "duration" else 130), stderr
        assert store.events()[-1].metadata["reason"] == "stopped"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
