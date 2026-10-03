"""Token-free event reports in stable ingestion order."""

from __future__ import annotations

import json
from collections.abc import Sequence

from .models import TOKEN_PATTERN, Canary, Event


def redact_text(value: str) -> str:
    return TOKEN_PATTERN.sub("[canary]", value)


def render_report(
    events: Sequence[Event],
    *,
    format: str = "text",
    canaries: Sequence[Canary] = (),
) -> str:
    """Serialize stored events without artifact contents or token values."""
    kinds = {canary.id: canary.kind for canary in canaries}
    records = [
        dict(event.to_dict(), canary_type=kinds.get(event.canary_id or "")) for event in events
    ]
    if format == "json":
        output = json.dumps({"events": records, "count": len(records)}, indent=2, sort_keys=True)
    elif format == "jsonl":
        output = "\n".join(json.dumps(record, sort_keys=True) for record in records)
    elif format == "text":
        if not events:
            return "No events."
        lines = ["SEQ  TIMESTAMP  ACTION  TYPE  CANARY  SOURCE  PID  RUN  DESTINATION"]
        for event in events:
            lines.append(
                f"{event.seq}  {event.timestamp}  {event.action.value}  "
                f"{kinds.get(event.canary_id or '', '-')}  "
                f"{event.canary_id or '-'}  {event.source}  "
                f"{event.pid if event.pid is not None else 'unknown'}  "
                f"{event.run_id or '-'}  {event.destination or '-'}"
            )
        output = "\n".join(lines)
    else:
        raise ValueError("report format must be text, json or jsonl")
    return redact_text(output)
