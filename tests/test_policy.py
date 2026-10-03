import http.client
import json
import os
import subprocess
import sys
import time

import pytest

from agentcanary import (
    Action,
    BlockingProxy,
    Event,
    IgnoreRule,
    InotifyMonitor,
    Observer,
    Policy,
    PolicySink,
    Store,
    create_canary,
    load_policy,
)
from agentcanary.report import render_report


@pytest.fixture
def issued(tmp_path):
    store = Store(tmp_path / "state")
    return store, create_canary(store, tmp_path / "workspace", "token")


def test_strict_toml_exact_origins_and_conjunctive_rules(tmp_path, issued):
    store, canary = issued
    config = tmp_path / "policy.toml"
    config.write_text(
        'version = 1\nallow_origins = ["https://MODEL.invalid:443/"]\n'
        '[[ignore]]\nsource = "sdk"\naction = "READ"\n'
        f'canary_id = "{canary.id}"\n'
    )
    policy = load_policy(config)
    assert policy.allow_origins == {"https://model.invalid"}
    observer = Observer(store, policy=policy)
    observer.read(canary.path)
    observer.observe_model(canary.token, destination="https://model.invalid/v1/responses")
    assert store.events(action=Action.READ)[0].metadata["policy_decision"] == "ignored"
    assert store.events(action=Action.READ)[0].metadata["policy_rule"] == 1
    assert store.events(action=Action.MODEL_REQUEST)[0].metadata["policy_decision"] == "allowlisted"
    for url in (
        "https://model.invalid.other.invalid",
        "http://model.invalid",
        "https://model.invalid:444",
        "https://model.invalid@other.invalid",
        "https://other.invalid/?model.invalid",
    ):
        (event,) = observer.observe_model(canary.token, destination=url)
        assert event.metadata["policy_decision"] == "observed"
    for action, source, canary_id in (
        (Action.COPY, "sdk", canary.id),
        (Action.READ, "inotify", canary.id),
        (Action.READ, "sdk", "00000000-0000-0000-0000-000000000000"),
    ):
        event = policy.annotate(Event(action=action, source=source, canary_id=canary_id))
        assert event.metadata["policy_decision"] == "observed"


@pytest.mark.parametrize(
    "config",
    [
        "",
        "version = true",
        "version = 2",
        'version = "1"',
        "version = 1\nallow_origin = []",
        'version = 1\nallow_origins = "https://x.invalid"',
        "version = 1\nallow_origins = [42]",
        'version = 1\nallow_origins = ["https://x.invalid/path"]',
        'version = 1\nallow_origins = ["https://user:PRIVATE@x.invalid"]',
        'version = 1\nallow_origins = ["https://x.invalid?q=PRIVATE"]',
        'version = 1\nallow_origins = ["https://*.invalid"]',
        'version = 1\nallow_origins = ["ftp://x.invalid"]',
        'version = 1\nignore = "sdk"',
        "version = 1\n[[ignore]]",
        'version = 1\n[[ignore]]\nsorce = "sdk"',
        "version = 1\n[[ignore]]\nsource = 42",
        'version = 1\n[[ignore]]\nsource = "Invalid Source"',
        'version = 1\n[[ignore]]\naction = "PRIVATE_BAD_ACTION"',
        'version = 1\n[[ignore]]\ncanary_id = "PRIVATE_BAD_UUID"',
        'version = 1\nignored = "PRIVATE_MALFORMED',
    ],
)
def test_invalid_config_rejected_without_reflecting_values(tmp_path, config):
    path = tmp_path / "config"
    path.write_text(config)
    with pytest.raises(ValueError) as raised:
        load_policy(path)
    assert "PRIVATE" not in str(raised.value)


def test_config_io_bounds_and_no_side_effects(tmp_path):
    path = tmp_path / "config"
    path.write_bytes(b"x" * 65537)
    with pytest.raises(ValueError, match="64 KiB"):
        load_policy(path)
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        load_policy(path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        load_policy(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular"):
        load_policy(fifo)
    path.write_text("version = 1\nunknown = true")
    result = subprocess.run(
        [sys.executable, "-m", "agentcanary", "--config", str(path), "create", "env"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert not (tmp_path / ".agentcanary").exists()
    assert not (tmp_path / "canaries").exists()


def test_protected_events_retained_and_report_filter_is_presentation_only(issued):
    store, canary = issued
    policy = Policy(ignore=(IgnoreRule(source="sdk"), IgnoreRule(action=Action.CREATE)))
    sink = PolicySink(store, policy)
    created = store.events(action=Action.CREATE)[0]
    assert policy.annotate(created) is created
    health = Event(action=Action.MONITOR_HEALTH, source="sdk", metadata={"healthy": False})
    assert policy.annotate(health) is health
    sink.record(health)
    Observer(store, sink=sink).read(canary.path)
    before = store.events()
    for format in ("text", "json", "jsonl"):
        report = render_report(before, canaries=store.canaries(), format=format)
        assert "ignored" in report
        assert "READ" in report
        hidden = render_report(before, canaries=store.canaries(), format=format, hide_policy=True)
        assert "READ" not in hidden
        assert "CREATE" in hidden
        assert "MONITOR_HEALTH" in hidden
    assert store.events() == before
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentcanary",
            "--state-dir",
            str(store.state_dir),
            "report",
            "--hide-policy",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert [event["action"] for event in json.loads(result.stdout)["events"]] == [
        "CREATE",
        "MONITOR_HEALTH",
    ]


def test_policy_never_allows_forwarding_and_applies_to_filesystem(issued):
    store, canary = issued
    policy = Policy(
        allow_origins=frozenset({"https://allowed.invalid"}), ignore=(IgnoreRule(source="inotify"),)
    )
    sink = PolicySink(store, policy)
    with BlockingProxy(store, sink=sink) as proxy:
        connection = http.client.HTTPConnection(proxy.host, proxy.port, timeout=3)
        connection.request("POST", "https://allowed.invalid/v1/responses", body=canary.token)
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.close()
    event = store.events(action=Action.EXFILTRATION)[0]
    assert event.metadata["policy_decision"] == "allowlisted"
    assert event.metadata["blocked"] is True
    with InotifyMonitor(store, store.state_dir.parent / "workspace", sink=sink) as monitor:
        with open(canary.path, "rb") as stream:
            stream.read()
        deadline = time.monotonic() + 3
        while not store.events(action=Action.READ):
            assert time.monotonic() < deadline
            monitor.check()
            time.sleep(0.01)
    assert store.events(action=Action.READ)[0].metadata["policy_decision"] == "ignored"


def test_argument_snapshot_matches_actual_invocation_after_sink_mutation(issued, monkeypatch):
    store, canary = issued
    argv = ["fixture-command", canary.token]
    invoked = []

    class MutatingSink:
        def record(self, event):
            argv[:] = ["different-command", "unobserved"]
            return store.record(event)

    def execute(arguments, **kwargs):
        invoked.append(arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(subprocess, "run", execute)
    result = Observer(store, sink=MutatingSink()).run_tool(argv)
    assert invoked == [["fixture-command", canary.token]]
    assert result.events[0].canary_id == canary.id
    assert argv == ["different-command", "unobserved"]
