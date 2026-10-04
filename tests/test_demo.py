import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentcanary import Action, InotifyMonitor, Store, demo
from agentcanary.demo import LIFECYCLE, DemoError, run_demo


def test_installed_cli_demo_complete_safe_reports_and_attribution(tmp_path):
    output = tmp_path / "demo"
    completed = subprocess.run(
        [sys.executable, "-m", "agentcanary", "demo", "--directory", str(output), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary == json.loads((output / "summary.json").read_text())
    assert summary["status"] == "complete"
    assert summary["actions"] == list(LIFECYCLE)
    assert summary["http_statuses"] == [403, 403]
    assert len({summary["child_pid"], summary["tool_pid"], os.getpid()}) == 3
    assert not Path(f"/proc/{summary['child_pid']}").exists()
    assert not Path(f"/proc/{summary['tool_pid']}").exists()
    store = Store(output / "state")
    canary = store.canaries()[0]
    events = store.events(canary_id=canary.id)
    assert {event.action.value for event in events} == set(LIFECYCLE)
    assert all(event.run_id == summary["run_id"] for event in events)
    sdk = [event for event in events if event.source == "sdk"]
    assert [event.action for event in sdk] == [
        Action.READ,
        Action.COPY,
        Action.TOOL_USE,
        Action.MODEL_REQUEST,
    ]
    assert all(event.pid == summary["child_pid"] for event in sdk)
    assert all(event.pid is None for event in events if event.source in ("inotify", "http"))
    assert (output / "workspace/source.env").read_bytes() == (
        output / "workspace/copy.env"
    ).read_bytes()
    for name in ("summary.json", "events.jsonl", "report.txt", "child.json", "tool.json"):
        assert canary.token not in (output / name).read_text()
    assert canary.token not in completed.stdout + completed.stderr
    exported = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
    assert [item["seq"] for item in exported] == [event.seq for event in store.events()]
    assert output.stat().st_mode & 0o777 == 0o700
    assert not (tmp_path / ".agentcanary").exists()
    report = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentcanary",
            "--state-dir",
            summary["state_dir"],
            "report",
            "--format",
            "jsonl",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert report.returncode == 0, report.stderr
    assert report.stdout == (output / "events.jsonl").read_text()


def test_new_directory_required_and_symlink_components_refused(tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "retain"
    sentinel.write_text("untouched")
    with pytest.raises(FileExistsError):
        run_demo(existing)
    link = tmp_path / "link"
    link.symlink_to(existing, target_is_directory=True)
    with pytest.raises(OSError):
        run_demo(link / "new")
    with pytest.raises(OSError):
        run_demo(link)
    assert sentinel.read_text() == "untouched"
    assert sorted(path.name for path in existing.iterdir()) == ["retain"]


def test_repeated_default_runs_are_unique(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first, second = run_demo(), run_demo()
    assert first.directory != second.directory
    assert first.run_id != second.run_id
    assert first.canary_id != second.canary_id
    assert set(Path(first.directory).parent.iterdir()) == {
        Path(first.directory),
        Path(second.directory),
    }


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_has_no_filesystem_side_effect(tmp_path, timeout):
    with pytest.raises(ValueError):
        run_demo(tmp_path / "demo", timeout=timeout)
    assert not list(tmp_path.iterdir())


@pytest.fixture
def workers(monkeypatch):
    instances = []
    for name in ("InotifyMonitor", "BlockingProxy"):
        original = getattr(demo, name)

        def factory(*args, cls=original, **kwargs):
            instance = cls(*args, **kwargs)
            instances.append(instance)
            return instance

        monkeypatch.setattr(demo, name, factory)
    yield instances
    assert all(not instance.running for instance in instances)
    assert not any(thread.name.startswith("agentcanary-") for thread in threading.enumerate())


@pytest.mark.parametrize("worker", [demo.InotifyMonitor, demo.BlockingProxy])
def test_startup_failure_retains_failed_evidence(tmp_path, monkeypatch, workers, worker):
    def fail(self):
        raise OSError("simulated start failure")

    monkeypatch.setattr(worker, "start", fail)
    output = tmp_path / "demo"
    with pytest.raises(DemoError):
        run_demo(output)
    assert json.loads((output / "summary.json").read_text())["status"] == "failed"
    assert Store(output / "state").events(action=Action.CREATE)
    assert not (output / "child.json").exists()


def test_zero_watches_fail_before_child_start(tmp_path, monkeypatch, workers):
    monkeypatch.setattr(
        InotifyMonitor,
        "watch_count",
        property(lambda self: 0),
    )
    with pytest.raises(DemoError, match="coverage"):
        run_demo(tmp_path / "demo")
    assert not (tmp_path / "demo/child.json").exists()


def test_http_sink_failure_cannot_become_a_success(tmp_path, monkeypatch, workers):
    original = Store.record

    def fail_http(self, event):
        if event.source == "http":
            raise OSError("simulated sink failure")
        return original(self, event)

    monkeypatch.setattr(Store, "record", fail_http)
    output = tmp_path / "demo"
    with pytest.raises(DemoError):
        run_demo(output)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert "actions" not in summary
    assert Store(output / "state").events(action=Action.TOOL_USE)


def test_missing_passive_read_fails_at_deadline(tmp_path, monkeypatch, workers):
    monkeypatch.setattr(InotifyMonitor, "_process", lambda self, data: None)
    original_exit_code = demo._child_exit_code
    child_finished = False

    def exit_code(child):
        nonlocal child_finished
        code = original_exit_code(child)
        child_finished = code == 0
        return code

    def monotonic():
        return time.monotonic() + (30 if child_finished else 0)

    # Let the real child finish before expiring the missing-evidence deadline.
    # Keep the worker threads' clocks unchanged.
    monkeypatch.setattr(demo, "_child_exit_code", exit_code)
    monkeypatch.setattr(demo, "time", SimpleNamespace(monotonic=monotonic, sleep=time.sleep))
    output = tmp_path / "demo"
    with pytest.raises(DemoError, match="passive read evidence"):
        run_demo(output)
    assert (output / "child.json").exists()
    assert json.loads((output / "summary.json").read_text())["status"] == "failed"


def test_export_failure_is_failure_even_after_complete_chain(tmp_path, monkeypatch, workers):
    original = demo._write

    def fail_report(path, content):
        if path.name == "report.txt":
            raise OSError("simulated disk failure")
        return original(path, content)

    monkeypatch.setattr(demo, "_write", fail_report)
    output = tmp_path / "demo"
    with pytest.raises(DemoError):
        run_demo(output)
    assert json.loads((output / "summary.json").read_text())["status"] == "failed"
    assert (output / "events.jsonl").exists()


# The tool and its grandchild ignore SIGTERM to exercise forced descendant reaping.
GRANDCHILD = """
import os,signal,sys
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path(sys.argv[1], 'grandchild.pid').write_text(str(os.getpid()))
signal.pause()
"""
TOOL = f"""
import os,signal,subprocess,sys
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path(sys.argv[1], 'tool.pid').write_text(str(os.getpid()))
subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}, sys.argv[1]])
signal.pause()
"""


def child_script(mode):
    return f"""
import os,subprocess,sys,time
from pathlib import Path
from agentcanary import demo
from agentcanary import Observer,Store
def simulation(directory, run_id, port):
    Path(directory, 'agent.pid').write_text(str(os.getpid()))
    argv = [sys.executable, '-c', {TOOL!r}, str(directory)]
    if {mode!r} == 'failure':
        subprocess.Popen(argv)
        deadline = time.monotonic() + 3
        while not Path(directory, 'grandchild.pid').exists():
            assert time.monotonic() < deadline
            time.sleep(0.005)
        raise RuntimeError('simulated failure with descendants')
    observer = Observer(Store(directory / 'state'), run_id=run_id)
    observer.run_tool(argv, input=observer.read(directory / 'workspace/source.env'), timeout=30)
demo._simulate = simulation
raise SystemExit(demo._main())
"""


@pytest.mark.parametrize("mode", ["failure", "timeout", "interrupt"])
def test_failure_timeout_and_interruption_reap_owned_descendants(
    tmp_path, monkeypatch, workers, mode
):
    script = child_script(mode)
    original = demo._child_command

    def command(directory, run_id, port):
        return [sys.executable, "-c", script, *original(directory, run_id, port)[3:]]

    monkeypatch.setattr(demo, "_child_command", command)
    output = tmp_path / "demo"
    if mode == "interrupt":
        check = demo._check_workers

        def interrupted(monitor, proxy):
            check(monitor, proxy)
            if (output / "grandchild.pid").exists():
                raise KeyboardInterrupt

        monkeypatch.setattr(demo, "_check_workers", interrupted)
    started = time.monotonic()
    with pytest.raises(KeyboardInterrupt if mode == "interrupt" else DemoError):
        run_demo(output, timeout=1.5)
    assert time.monotonic() - started < 7
    for name in ("agent.pid", "tool.pid", "grandchild.pid"):
        pid = int((output / name).read_text())
        assert not Path(f"/proc/{pid}").exists(), f"unreaped {name}: {pid}"
    assert json.loads((output / "summary.json").read_text())["status"] == "failed"
    assert not (output / "child.json").exists()


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_cli_real_signal_interrupt_cleans_group(tmp_path, signum):
    output = tmp_path / "demo"
    script = f"""
import sys
from agentcanary import demo
from agentcanary.cli import main
original = demo._child_command
child_code = {child_script("timeout")!r}
def child_command(directory, run_id, port):
    return [sys.executable, '-c', child_code, *original(directory, run_id, port)[3:]]
demo._child_command = child_command
raise SystemExit(main(['demo', '--directory', {str(output)!r}, '--json']))
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not (output / "grandchild.pid").exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.005)
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=7)
        assert process.returncode == 130, stderr
        assert stdout == ""
        assert "interrupted" in stderr
        for name in ("agent.pid", "tool.pid", "grandchild.pid"):
            assert not Path(f"/proc/{int((output / name).read_text())}").exists()
        assert json.loads((output / "summary.json").read_text())["status"] == "failed"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
