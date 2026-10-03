"""Release review regressions: publication failure and process ownership boundaries."""

import json
import os
import signal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentcanary import demo


@pytest.mark.parametrize("persistent", [False, True])
def test_final_summary_fsync_failure_never_publishes_complete(tmp_path, monkeypatch, persistent):
    output = tmp_path / "demo"
    write = demo._write
    link = os.link
    published = []
    failed = False

    def publish(source, destination, **kwargs):
        if destination == "summary.json":
            # The public path must not exist until its flushed content is linked.
            assert not (output / "summary.json").exists()
            published.append(json.loads((output / source).read_text())["status"])
        return link(source, destination, **kwargs)

    def fail_fsync(fd):
        nonlocal failed
        failed = True
        raise OSError("simulated summary fsync failure")

    def write_summary(path, content):
        if path.name == "summary.json" and (persistent or not failed):
            with monkeypatch.context() as scoped:
                scoped.setattr(demo.os, "fsync", fail_fsync)
                return write(path, content)
        return write(path, content)

    monkeypatch.setattr(demo.os, "link", publish)
    monkeypatch.setattr(demo, "_write", write_summary)
    with pytest.raises(demo.DemoError, match="output directory"):
        demo.run_demo(output)
    assert failed
    if persistent:
        assert not (output / "summary.json").exists()
        assert published == []
    else:
        assert json.loads((output / "summary.json").read_text())["status"] == "failed"
        assert published == ["failed"]
    assert not list(output.glob(".*.tmp"))
    assert (output / "events.jsonl").exists()


@pytest.mark.parametrize("symlink", [False, True])
def test_report_publication_never_replaces_existing_destination(tmp_path, symlink):
    destination = tmp_path / "summary.json"
    retained = tmp_path / "retained.json"
    retained.write_text("existing operator content")
    if symlink:
        destination.symlink_to(retained)
    else:
        destination.write_text("existing operator content")
    with pytest.raises(FileExistsError):
        demo._write(destination, '{"status":"complete"}')
    assert destination.read_text() == "existing operator content"
    assert retained.read_text() == "existing operator content"
    assert destination.is_symlink() is symlink
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("expired", [False, True])
def test_group_signals_finish_before_leader_is_reaped(monkeypatch, expired):
    child = Mock(pid=12345, returncode=None)
    calls = []
    clock = iter([0.0, 3.0])
    monkeypatch.setattr(demo.time, "monotonic", lambda: next(clock))

    def observe(kind, pid, options):
        assert kind == os.P_PID and pid == child.pid
        assert options & os.WNOWAIT and options & os.WNOHANG and options & os.WEXITED
        assert child.returncode is None
        calls.append("observe")
        return None if expired else SimpleNamespace(si_status=0, si_code=os.CLD_EXITED)

    def signal_group(pid, signum):
        assert pid == child.pid
        assert child.returncode is None
        calls.append(signum)

    def reap(timeout):
        assert timeout == 2
        assert calls[-1] == signal.SIGKILL
        child.returncode = 0
        calls.append("reap")
        return 0

    child.wait.side_effect = reap
    monkeypatch.setattr(demo.os, "waitid", observe)
    monkeypatch.setattr(demo.os, "killpg", signal_group)
    demo._stop_child(child)
    assert [item for item in calls if item in (signal.SIGTERM, signal.SIGKILL, "reap")] == [
        signal.SIGTERM,
        signal.SIGKILL,
        "reap",
    ]
    assert calls[-1] == "reap"


@pytest.mark.parametrize("external_reap", ["already_reported", "before_term", "before_kill"])
def test_cleanup_does_not_signal_a_reaped_child_group(monkeypatch, external_reap):
    child = Mock(pid=12345, returncode=0 if external_reap == "already_reported" else None)
    signals = []
    observations = 0

    def observe(*args):
        nonlocal observations
        observations += 1
        if external_reap == "before_kill" and observations <= 2:
            return SimpleNamespace(si_status=0, si_code=os.CLD_EXITED)
        raise ChildProcessError("external waiter reaped the leader")

    monkeypatch.setattr(demo.os, "waitid", observe)
    monkeypatch.setattr(demo.os, "killpg", lambda pid, signum: signals.append(signum))
    demo._stop_child(child)
    assert signals == ([signal.SIGTERM] if external_reap == "before_kill" else [])
    child.wait.assert_not_called()


def test_complete_agent_remains_waitable_until_cleanup_and_sends_structured_model_input(
    tmp_path, monkeypatch
):
    spawned = []
    requests = []
    popen = demo.subprocess.Popen
    verify = demo._verify_chain
    request = demo.BlockingProxy._request

    def launch(*args, **kwargs):
        child = popen(*args, **kwargs)
        spawned.append(child)
        return child

    def verify_unreaped(*args):
        child = spawned[0]
        assert child.returncode is None
        status = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        assert status is not None and status.si_status == 0
        verify(*args)

    def record_request(self, connection):
        parsed = request(self, connection)
        requests.append(parsed)
        return parsed

    monkeypatch.setattr(demo.subprocess, "Popen", launch)
    monkeypatch.setattr(demo, "_verify_chain", verify_unreaped)
    monkeypatch.setattr(demo.BlockingProxy, "_request", record_request)
    result = demo.run_demo(tmp_path / "demo")
    assert result.status == "complete"
    assert spawned[0].returncode == 0
    method, target, headers, body = requests[0]
    assert method == "POST" and target == demo.MODEL_TARGET
    assert (
        dict((name.lower(), value) for name, value in headers)["content-type"] == "application/json"
    )
    assert json.loads(body) == {
        "model": "synthetic-demo",
        "input": (tmp_path / "demo/workspace/source.env").read_text(),
    }
    assert requests[1][1] == demo.COLLECTOR_TARGET
    assert requests[1][3] == (tmp_path / "demo/workspace/source.env").read_bytes()
