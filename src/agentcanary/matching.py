"""Bounded matching against an explicit, immutable issued-marker snapshot."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .models import TOKEN_PATTERN, Canary

DEFAULT_MAX_BYTES = 1024 * 1024
_MARKER = re.compile(TOKEN_PATTERN.pattern.encode() + rb"(?![0-9a-f])")


class PayloadTooLarge(ValueError):
    """Input exceeds the configured scan bound; it was not fully inspected."""


def bounded_bytes(payload: bytes | str, limit: int) -> bytes:
    if not isinstance(payload, (bytes, str)):
        raise TypeError("payload must be bytes or text")
    if len(payload) > limit:
        raise PayloadTooLarge("payload exceeds observation byte limit")
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(data) > limit:
        raise PayloadTooLarge("payload exceeds observation byte limit")
    return data


@dataclass(frozen=True, slots=True)
class MatchResult:
    canaries: tuple[Canary, ...]
    bytes_scanned: int


class TokenMatcher:
    """Refresh by constructing a new matcher; no registry I/O occurs during matching."""

    def __init__(self, canaries: Iterable[Canary], *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        if type(max_bytes) is not int or not 1 <= max_bytes <= 16 * DEFAULT_MAX_BYTES:
            raise ValueError("max_bytes must be between 1 byte and 16 MiB")
        self.max_bytes = max_bytes
        self._issued = {canary.token.encode("ascii"): canary for canary in canaries}

    def match(self, payload: bytes | str) -> MatchResult:
        data = bounded_bytes(payload, self.max_bytes)
        found: dict[str, Canary] = {}
        for marker in _MARKER.finditer(data):
            canary = self._issued.get(marker.group())
            if canary is not None:
                found[canary.id] = canary
        return MatchResult(tuple(found.values()), len(data))
