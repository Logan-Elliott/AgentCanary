"""Strict local policy annotates retained audit evidence; it never authorizes forwarding."""

from __future__ import annotations

import os
import re
import stat
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from .filesystem import absolute_path, open_directory
from .models import TOKEN_PATTERN, Action, Event
from .network import safe_origin
from .protocols import EventSink

MAX_CONFIG_BYTES = 65536


def _origin(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("allow_origins must contain HTTP(S) origin strings")
    try:
        parsed = urlsplit(value)
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or "?" in value
            or "#" in value
            or re.search(TOKEN_PATTERN.pattern, parsed.hostname or "", re.IGNORECASE)
        ):
            raise ValueError
        return safe_origin(value)
    except ValueError:
        raise ValueError(
            "allow_origins accepts only exact HTTP(S) origins without credentials"
        ) from None


@dataclass(frozen=True, slots=True)
class IgnoreRule:
    """All supplied selectors must match. At least one selector is required."""

    source: str | None = None
    action: Action | None = None
    canary_id: str | None = None

    def __post_init__(self) -> None:
        if self.source is None and self.action is None and self.canary_id is None:
            raise ValueError("ignore rule requires at least one selector")
        if self.source is not None and (
            not isinstance(self.source, str)
            or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.source) is None
        ):
            raise ValueError("ignore source must be a short lowercase identifier")
        if self.action is not None and not isinstance(self.action, Action):
            raise ValueError("ignore action must be an Action")
        if self.canary_id is not None:
            try:
                if (
                    not isinstance(self.canary_id, str)
                    or str(UUID(self.canary_id)) != self.canary_id
                ):
                    raise ValueError
            except ValueError:
                raise ValueError("ignore canary_id must be a canonical UUID") from None

    def matches(self, event: Event) -> bool:
        return (
            (self.source is None or self.source == event.source)
            and (self.action is None or self.action == event.action)
            and (self.canary_id is None or self.canary_id == event.canary_id)
        )


@dataclass(frozen=True, slots=True)
class Policy:
    allow_origins: frozenset[str] = frozenset()
    ignore: tuple[IgnoreRule, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.allow_origins, frozenset) or len(self.allow_origins) > 256:
            raise ValueError("allow_origins must be a frozenset of at most 256 origins")
        if (
            not isinstance(self.ignore, tuple)
            or len(self.ignore) > 256
            or not all(isinstance(rule, IgnoreRule) for rule in self.ignore)
        ):
            raise ValueError("ignore must be a tuple of at most 256 IgnoreRule values")
        object.__setattr__(self, "allow_origins", frozenset(_origin(v) for v in self.allow_origins))

    def annotate(self, event: Event) -> Event:
        if event.action in (Action.CREATE, Action.MONITOR_HEALTH):
            return event
        decision = "observed"
        rule_number: int | None = None
        for index, rule in enumerate(self.ignore, start=1):
            if rule.matches(event):
                decision, rule_number = "ignored", index
                break
        if (
            decision == "observed"
            and event.action in (Action.EXFILTRATION, Action.MODEL_REQUEST)
            and (event.destination in self.allow_origins)
            and event.metadata.get("destination_redacted") is not True
        ):
            decision = "allowlisted"
        metadata = dict(event.metadata)
        metadata["policy_decision"] = decision
        metadata.pop("policy_rule", None)
        if rule_number is not None:
            metadata["policy_rule"] = rule_number
        return replace(event, metadata=metadata)


class PolicySink:
    """Compose with any EventSink; record every event and return persisted annotations."""

    def __init__(self, sink: EventSink, policy: Policy) -> None:
        self.sink = sink
        self.policy = policy

    def record(self, event: Event) -> Event:
        return self.sink.record(self.policy.annotate(event))


def load_policy(path: str | Path) -> Policy:
    """Load an explicitly selected, bounded regular TOML file; no implicit config search."""
    selected = absolute_path(path)
    parent = open_directory(selected.parent)
    try:
        fd = os.open(
            selected.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent
        )
    finally:
        os.close(parent)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("policy config must be a regular file")
        raw = stream.read(MAX_CONFIG_BYTES + 1)
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("policy config exceeds 64 KiB")
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ValueError("policy config must be valid UTF-8 TOML") from None
    if set(data) - {"version", "allow_origins", "ignore"}:
        raise ValueError("policy config contains unknown fields")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("policy config requires version = 1")
    origins = data.get("allow_origins", [])
    if (
        not isinstance(origins, list)
        or len(origins) > 256
        or not all(isinstance(origin, str) for origin in origins)
    ):
        raise ValueError("allow_origins must be an array of at most 256 origin strings")
    rules = data.get("ignore", [])
    if not isinstance(rules, list) or len(rules) > 256:
        raise ValueError("ignore must be an array of at most 256 selector tables")
    parsed_rules = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {"source", "action", "canary_id"}:
            raise ValueError("ignore rule contains unknown fields")
        if not all(isinstance(value, str) for value in rule.values()):
            raise ValueError("ignore selectors must be strings")
        try:
            action = Action(rule["action"]) if "action" in rule else None
        except ValueError:
            raise ValueError("ignore action must be a known Action") from None
        parsed_rules.append(
            IgnoreRule(source=rule.get("source"), action=action, canary_id=rule.get("canary_id"))
        )
    return Policy(allow_origins=frozenset(origins), ignore=tuple(parsed_rules))
