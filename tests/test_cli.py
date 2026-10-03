import json
import subprocess
import sys
from pathlib import Path

from agentcanary import Action, Event, Store


def cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agentcanary", *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def test_cli_help_version_and_catalog_have_no_state_side_effect(tmp_path: Path) -> None:
    assert "--state-dir" in cli(tmp_path, "--help").stdout
    assert cli(tmp_path, "--version").stdout.strip() == "agentcanary 0.1.0"
    types = cli(tmp_path, "types", "--json")
    assert types.returncode == 0
    assert len(json.loads(types.stdout)["types"]) == 9
    assert not (tmp_path / ".agentcanary").exists()


def test_create_report_filters_json_jsonl_and_errors(tmp_path: Path) -> None:
    created = cli(
        tmp_path,
        "--state-dir",
        "state",
        "create",
        "openai-key",
        "--output",
        "config/key.env",
        "--root",
        "workspace",
        "--run-id",
        "one",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    record = json.loads(created.stdout)[0]
    assert "token" not in record
    store = Store(tmp_path / "state")
    item = store.get_canary(record["id"])
    assert item is not None
    store.record(
        Event(
            action=Action.READ,
            source="inotify",
            canary_id=item.id,
            run_id="two",
            provenance="kernel-notification",
        )
    )
    json_report = cli(tmp_path, "--state-dir", "state", "report", "--format", "json")
    assert json_report.returncode == 0, json_report.stderr
    assert item.token not in json_report.stdout
    events = json.loads(json_report.stdout)["events"]
    assert [event["seq"] for event in events] == [1, 2]
    assert events[1]["pid"] is None
    assert all(event["canary_type"] == "openai-key" for event in events)
    filtered = cli(
        tmp_path,
        "--state-dir",
        "state",
        "report",
        "--format",
        "jsonl",
        "--canary-id",
        item.id,
        "--action",
        "READ",
        "--run-id",
        "two",
    )
    assert len(filtered.stdout.splitlines()) == 1
    assert json.loads(filtered.stdout)["action"] == "READ"
    assert json.loads(filtered.stdout)["canary_type"] == "openai-key"
    text = cli(tmp_path, "--state-dir", "state", "report", "--after-seq", "1")
    assert "unknown" in text.stdout
    assert "CREATE" not in text.stdout
    again = cli(
        tmp_path,
        "--state-dir",
        "state",
        "create",
        "env",
        "--output",
        "config/key.env",
        "--root",
        "workspace",
    )
    assert again.returncode == 2
    assert "already exists" in again.stderr
    assert "Traceback" not in again.stderr
    invalid = cli(tmp_path, "--state-dir", "state", "report", "--limit", "0")
    assert invalid.returncode == 2
    assert len(store.canaries()) == 1


def test_seed_custom_templates_and_invalid_utf8(tmp_path: Path) -> None:
    seeded = cli(tmp_path, "seed", "workspace", "--profile", "realistic", "--json")
    assert seeded.returncode == 0, seeded.stderr
    assert len(json.loads(seeded.stdout)) == 8
    template = tmp_path / "template.txt"
    template.write_text("PRIVATE_REFERENCE=$token\nID=$canary_id\n")
    created = cli(
        tmp_path,
        "create",
        "custom",
        "--output",
        "custom.txt",
        "--root",
        "workspace",
        "--template",
        str(template),
    )
    assert created.returncode == 0, created.stderr
    assert "SYNTHETIC ONLY" in (tmp_path / "workspace/custom.txt").read_text()
    template.write_bytes(b"\xff")
    bad = cli(tmp_path, "create", "custom", "--output", "bad.txt", "--template", str(template))
    assert bad.returncode == 2
    assert "Traceback" not in bad.stderr
    missing = cli(tmp_path, "create", "custom", "--output", "bad.txt")
    assert missing.returncode == 2


def test_empty_reports_are_machine_readable(tmp_path: Path) -> None:
    assert json.loads(cli(tmp_path, "report", "--format", "json").stdout) == {
        "events": [],
        "count": 0,
    }
    assert cli(tmp_path, "report", "--format", "jsonl").stdout == ""
    assert cli(tmp_path, "report").stdout == "No events.\n"


def test_create_type_generates_a_safe_unique_default_destination(tmp_path: Path) -> None:
    for kind in ("aws-key", "kubeconfig", "aws-key"):
        result = cli(tmp_path, "create", kind, "--json")
        assert result.returncode == 0, result.stderr
        record = json.loads(result.stdout)[0]
        assert record["kind"] == kind
        assert Path(record["path"]).parent == tmp_path / "canaries"
        assert Path(record["path"]).is_file()
    assert len(list((tmp_path / "canaries").iterdir())) == 3
