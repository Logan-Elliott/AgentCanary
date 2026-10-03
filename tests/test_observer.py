import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentcanary import (
    Action,
    Observer,
    PayloadTooLarge,
    Store,
    TokenMatcher,
    ToolInvocationError,
    create_canary,
)


def setup(tmp_path):
    store = Store(tmp_path / "state")
    canary = create_canary(store, tmp_path / "workspace", "token.env")
    return store, canary, Observer(store, run_id="test-run")


def test_exact_matching_and_bounds(tmp_path):
    store, canary, _ = setup(tmp_path)
    matcher = TokenMatcher(store.canaries(), max_bytes=1024)
    for payload in (
        b"",
        "unknown",
        canary.token[:-1],
        "AGENTCANARY_SYNTHETIC_" + "0" * 32,
    ):
        assert matcher.match(payload).canaries == ()
    result = matcher.match((canary.token + " " + canary.token).encode())
    assert result.canaries == (canary,)
    assert matcher.match(b"before" + canary.token.encode() + b"deadbeef").canaries == (canary,)
    assert canary.token not in repr(result)
    with pytest.raises(PayloadTooLarge):
        matcher.match("é" * 600)
    with pytest.raises(TypeError):
        matcher.match(None)
    with pytest.raises(ValueError):
        TokenMatcher([], max_bytes=0)


def test_read_copy_and_relocated_content(tmp_path):
    store, canary, observer = setup(tmp_path)
    data = observer.read(canary.path)
    copy = tmp_path / "copy"
    events = observer.copy(canary.path, copy)
    assert copy.read_bytes() == data
    assert copy.stat().st_mode & 0o777 == 0o600
    assert events[0].action == Action.COPY
    assert events[0].destination == str(copy)
    observer.read(copy)
    reads = store.events(action=Action.READ)
    assert len(reads) == 2
    assert all(
        event.canary_id == canary.id and event.pid == os.getpid() and event.run_id == "test-run"
        for event in reads
    )
    with pytest.raises(FileExistsError):
        observer.copy(canary.path, copy)
    assert len(store.events(action=Action.COPY)) == 1


def test_symlink_fifo_and_failed_reads(tmp_path):
    store, canary, observer = setup(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(canary.path)
    for method in (observer.read, lambda path: observer.copy(path, tmp_path / "out")):
        with pytest.raises((OSError, ValueError)):
            method(link)
        with pytest.raises((OSError, ValueError)):
            method(tmp_path)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        observer.read(fifo)
    with pytest.raises(OSError):
        observer.copy(canary.path, link)
    assert not store.events(action=Action.READ)
    assert not store.events(action=Action.COPY)


def test_snapshot_refresh_and_generic_model_input(tmp_path):
    store, _, observer = setup(tmp_path)
    later = create_canary(store, tmp_path / "workspace", "later")
    assert not observer.observe(Action.MODEL_REQUEST, later.token)
    observer.refresh()
    events = observer.observe(Action.MODEL_REQUEST, later.token, metadata={"model": "fixture"})
    assert events[0].provenance == "sdk_input"
    assert events[0].metadata["attribution"] == "caller_pid"
    with pytest.raises(ValueError):
        observer.observe(Action.CREATE, later.token)
    with pytest.raises(ValueError):
        observer.observe(Action.READ, b"", metadata={"argv": "hidden"})


def test_tool_input_and_real_invocation_do_not_persist_content(tmp_path):
    store, canary, observer = setup(tmp_path)
    observed = observer.observe_tool(canary.token, tool="fixture")
    assert observed[0].metadata["operation"] == "input_observed"
    target = tmp_path / "stdin"
    code = "import sys,pathlib; pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())"
    result = observer.run_tool([sys.executable, "-c", code, str(target)], input=canary.token)
    assert result.returncode == 0
    assert target.read_text() == canary.token
    assert result.events[0].metadata["operation"] == "invocation_attempt"
    assert result.events[0].provenance == "sdk_tool_invocation_input"
    assert canary.token not in repr(store.events())
    assert code not in repr(store.events())
    with pytest.raises(ToolInvocationError):
        observer.run_tool([str(tmp_path / "absent"), canary.token])
    assert len(store.events(action=Action.TOOL_USE)) == 3
    assert store.events(action=Action.MONITOR_HEALTH)[-1].metadata["reason"] == "tool_failed"
    with pytest.raises(ValueError):
        observer.run_tool("echo accidental-shell")


def test_real_sdk_process_attribution(tmp_path):
    store, canary, _ = setup(tmp_path)
    code = (
        "import os,sys; from agentcanary import Observer,Store; "
        "Observer(Store(sys.argv[1]),run_id='child').read(sys.argv[2]); print(os.getpid())"
    )
    child = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "state"), canary.path],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    event = store.events(action=Action.READ)[0]
    assert event.pid == int(child.stdout)
    assert event.pid != os.getpid()
    assert event.run_id == "child"


def test_oversized_input_is_diagnostic(tmp_path):
    store, canary, _ = setup(tmp_path)
    observer = Observer(store, max_bytes=64)
    with pytest.raises(PayloadTooLarge):
        observer.observe(Action.READ, b"x" * 65)
    with pytest.raises(PayloadTooLarge):
        observer.read(canary.path)
    assert not store.events(action=Action.READ)
    assert len(store.events(action=Action.MONITOR_HEALTH)) == 2


def test_sink_failure_is_visible(tmp_path):
    store, canary, _ = setup(tmp_path)

    class FailedSink:
        def record(self, event):
            raise RuntimeError("fixture sink unavailable")

    with pytest.raises(RuntimeError, match="fixture sink"):
        Observer(store, sink=FailedSink()).read(Path(canary.path))
