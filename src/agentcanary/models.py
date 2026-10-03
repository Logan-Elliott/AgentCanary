"""Immutable evidence records. No artifact content belongs in events."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TypeAlias
from uuid import UUID, uuid4

Scalar: TypeAlias = str | int | float | bool | None
TOKEN_PREFIX = "AGENTCANARY_SYNTHETIC_"
TOKEN_PATTERN = re.compile(r"AGENTCANARY_SYNTHETIC_[0-9a-f]{32}")
# Keep this explicit: adapters add reviewed evidence fields, never raw request data.
METADATA_KEYS = frozenset(
    {
        "backend",
        "reason",
        "error_code",
        "operation",
        "tool",
        "model",
        "method",
        "content_type",
        "content_encoding",
        "encoding",
        "matched_encoding",
        "match_count",
        "bytes",
        "bytes_read",
        "bytes_scanned",
        "body_bytes",
        "truncated",
        "status_code",
        "watch_count",
        "missing_count",
        "dropped_events",
        "mask",
        "cookie",
        "path",
        "original_path",
        "target_path",
        "attribution",
        "confidence",
        "blocked",
        "healthy",
        "host",
        "port",
        "scheme",
        "route",
        "protocol",
        "count",
        "detail",
        "sha256",
        "policy_decision",
        "policy_rule",
    }
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _label(value: str, name: str, limit: int = 512) -> None:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError(f"{name} must be a nonempty string of at most {limit} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{name} contains a control character")


def _timestamp(value: str) -> None:
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")


def _uuid(value: str) -> None:
    if str(UUID(value)) != value:
        raise ValueError("identifier must be a canonical UUID")


def safe_metadata(metadata: Mapping[str, Scalar]) -> Mapping[str, Scalar]:
    copied: dict[str, Scalar] = {}
    if len(metadata) > 32:
        raise ValueError("metadata exceeds 32 fields")
    for key, value in metadata.items():
        if key not in METADATA_KEYS:
            raise ValueError(f"unsupported metadata field: {key}")
        if value is not None and type(value) not in (str, int, float, bool):
            raise ValueError("metadata values must be JSON scalars")
        if isinstance(value, str):
            _label(value, "metadata value", 512)
            value = TOKEN_PATTERN.sub("[canary]", value)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("metadata numbers must be finite")
        copied[key] = value
    if len(json.dumps(copied).encode()) > 4096:
        raise ValueError("metadata exceeds 4096 bytes")
    return MappingProxyType(copied)


class Action(StrEnum):
    CREATE = "CREATE"
    READ = "READ"
    COPY = "COPY"
    TOOL_USE = "TOOL_USE"
    MODEL_REQUEST = "MODEL_REQUEST"
    EXFILTRATION = "EXFILTRATION"
    MONITOR_HEALTH = "MONITOR_HEALTH"


@dataclass(frozen=True, slots=True, kw_only=True)
class Canary:
    kind: str
    token: str = field(repr=False)
    path: str
    sha256: str
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _uuid(self.id)
        _timestamp(self.created_at)
        _label(self.kind, "kind", 64)
        _label(self.path, "path", 4096)
        if TOKEN_PATTERN.fullmatch(self.token) is None:
            raise ValueError("token must be an issued synthetic marker")
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("sha256 must be a hexadecimal SHA-256 digest")

    def to_dict(self, *, include_token: bool = False) -> dict[str, Scalar]:
        result: dict[str, Scalar] = {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
            "created_at": self.created_at,
        }
        if include_token:
            result["token"] = self.token
        return result


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    action: Action
    source: str
    canary_id: str | None = None
    provenance: str = "direct"
    run_id: str | None = None
    pid: int | None = None
    destination: str | None = None
    metadata: Mapping[str, Scalar] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=utc_now)
    seq: int | None = None

    def __post_init__(self) -> None:
        _uuid(self.id)
        _timestamp(self.timestamp)
        if not isinstance(self.action, Action):
            raise ValueError("action must be an Action")
        if self.canary_id is not None:
            _uuid(self.canary_id)
        elif self.action != Action.MONITOR_HEALTH:
            raise ValueError("canary_id is required for canary events")
        _label(self.source, "source", 128)
        _label(self.provenance, "provenance", 128)
        if self.run_id is not None:
            _label(self.run_id, "run_id", 128)
        if self.pid is not None and (type(self.pid) is not int or self.pid <= 0):
            raise ValueError("pid must be positive or unknown (None)")
        if self.seq is not None and (type(self.seq) is not int or self.seq <= 0):
            raise ValueError("seq must be positive or unassigned (None)")
        if self.destination is not None:
            _label(self.destination, "destination", 4096)
        object.__setattr__(self, "metadata", safe_metadata(self.metadata))

    def to_dict(self) -> dict[str, object]:
        return {
            "seq": self.seq,
            "id": self.id,
            "timestamp": self.timestamp,
            "canary_id": self.canary_id,
            "action": self.action.value,
            "source": self.source,
            "provenance": self.provenance,
            "run_id": self.run_id,
            "pid": self.pid,
            "destination": self.destination,
            "metadata": dict(self.metadata),
        }
