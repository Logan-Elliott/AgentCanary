"""Defensive parsing and policy identity contracts."""

import pytest

from agentcanary import Action, DecodeError, HTTPInspector, Observer, Policy, Store, create_canary
from agentcanary.models import Event


@pytest.fixture
def issued(tmp_path):
    store = Store(tmp_path / "state")
    canary = create_canary(store, tmp_path / "workspace", "canary")
    return store, canary


@pytest.mark.parametrize("redacted,expected", [(False, "allowlisted"), (True, "observed")])
def test_policy_requires_preserved_destination_identity(issued, redacted, expected):
    _, canary = issued
    policy = Policy(allow_origins=frozenset({"https://redacted.invalid"}))
    event = Event(
        action=Action.MODEL_REQUEST,
        source="sdk",
        canary_id=canary.id,
        destination="https://redacted.invalid",
        metadata={"destination_redacted": redacted},
    )
    assert policy.annotate(event).metadata["policy_decision"] == expected


def test_origin_redaction_is_explicit_and_never_persists_marker(issued):
    store, canary = issued
    observer = Observer(store, policy=Policy())
    destination = f"https://{canary.token}.invalid/v1/responses"
    (event,) = observer.observe_model(canary.token, destination=destination)
    assert event.destination == "https://redacted.invalid"
    assert event.metadata["destination_redacted"] is True
    assert event.metadata["policy_decision"] == "observed"
    assert canary.token.lower() not in repr(event).lower()
    events = observer.observe_http("POST", destination, body=canary.token)
    assert len(events) == 2
    assert all(event.metadata["destination_redacted"] is True for event in events)
    with pytest.raises(ValueError, match="exact HTTP"):
        Policy(allow_origins=frozenset({destination.removesuffix("/v1/responses")}))


@pytest.mark.parametrize(
    "payload",
    ['{"note":"first","note":"second"}', '{"outer":{"note":1,"note":2}}'],
)
def test_duplicate_json_members_report_incomplete_inspection(issued, payload):
    store, _ = issued
    inspector = HTTPInspector(store)
    with pytest.raises(DecodeError, match="duplicate_json_key"):
        inspector.inspect_model(payload, destination="https://model.invalid")
    (event,) = store.events(action=Action.MONITOR_HEALTH)
    assert event.metadata["reason"] == "duplicate_json_key"
    assert not store.events(action=Action.MODEL_REQUEST)


def test_same_json_member_name_in_separate_objects_is_valid(issued):
    store, _ = issued
    assert not HTTPInspector(store).inspect_model(
        '[{"note":"first"},{"note":"second"}]', destination="https://model.invalid"
    )
    assert not store.events(action=Action.MONITOR_HEALTH)
