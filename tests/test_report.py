import json
from uuid import uuid4

import pytest

from agentcanary import Action, Event
from agentcanary.report import render_report


@pytest.mark.parametrize("format", ["text", "json", "jsonl"])
def test_reports_redact_token_values_even_in_labels(format: str) -> None:
    token = "AGENTCANARY_SYNTHETIC_" + uuid4().hex
    event = Event(
        action=Action.MONITOR_HEALTH,
        source="test",
        run_id=token,
        destination=f"https://collector.invalid/{token}",
        metadata={"reason": token},
    )
    report = render_report([event], format=format)
    assert token not in report
    assert "[canary]" in report
    if format != "text":
        json.loads(report)
