"""Monitor cancellation and unsupported registry shapes fail explicitly."""

import hashlib
import os
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from agentcanary import Action, InotifyMonitor, MonitorError, Store, create_canary, generate


def test_stop_after_thread_start_failure_is_a_monitor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    create_canary(store, root, "artifact.env")
    monitor = InotifyMonitor(store, root)
    descriptors = len(os.listdir("/proc/self/fd"))

    def fail_start(thread: threading.Thread) -> None:
        raise RuntimeError("fixture thread start failure")

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", fail_start)
        with pytest.raises(MonitorError, match="startup failed"):
            monitor.start()
        with pytest.raises(MonitorError, match="startup failed"):
            monitor.stop()
    assert not monitor.running
    assert not monitor.ready.is_set()
    assert len(os.listdir("/proc/self/fd")) == descriptors
    with monitor:
        assert monitor.watch_count == 1


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_startup_cancellation_preserves_signal_and_releases_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interruption: type[BaseException]
) -> None:
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    create_canary(store, root, "artifact.env")
    monitor = InotifyMonitor(store, root)
    descriptors = len(os.listdir("/proc/self/fd"))

    def interrupt_snapshot(*args: object) -> None:
        raise interruption()

    with monkeypatch.context() as patch:
        patch.setattr(monitor, "_snapshot", interrupt_snapshot)
        with pytest.raises(interruption):
            monitor.start()
    monitor.stop()
    assert not monitor.running
    assert not monitor.ready.is_set()
    assert len(os.listdir("/proc/self/fd")) == descriptors
    assert store.events()[-1].metadata["reason"] == "startup_interrupted"


def test_duplicate_inode_is_diagnosed_without_replacing_original_canary(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    root.mkdir()
    path = root / "combined.env"
    first = generate("env", str(path))
    second = generate("env", str(path))
    content = (first.content + second.content).encode()
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    store.register_many(
        [replace(first.canary, sha256=digest), replace(second.canary, sha256=digest)]
    )
    # Registry order, not creation time, selects the supported first watch.
    expected, duplicate = store.canaries()
    with InotifyMonitor(store, root) as monitor:
        assert monitor.watch_count == 1
        assert any(
            event.canary_id == duplicate.id and event.metadata.get("reason") == "duplicate_inode"
            for event in store.events(action=Action.MONITOR_HEALTH)
        )
        path.read_bytes()
        deadline = time.monotonic() + 5
        while not store.events(action=Action.READ) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert {event.canary_id for event in store.events(action=Action.READ)} == {expected.id}
