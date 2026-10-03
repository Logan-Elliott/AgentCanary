import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentcanary import Action, Store
from agentcanary.demo import LIFECYCLE, run_demo


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
