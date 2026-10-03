"""Bounded matching against an explicit, immutable issued-marker snapshot."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from urllib.parse import unquote_to_bytes

from .models import TOKEN_PATTERN, Canary

DEFAULT_MAX_BYTES = 1024 * 1024
_MARKER = re.compile(TOKEN_PATTERN.pattern.encode())


class PayloadTooLarge(ValueError):
    """Input exceeds the configured scan bound; it was not fully inspected."""


class DecodeError(ValueError):
    """A representation could not be completely inspected; reason contains no input."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"representation inspection incomplete: {reason}")


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


@dataclass(frozen=True, slots=True)
class EncodedMatch:
    canary: Canary
    encoding: str


@dataclass(frozen=True, slots=True)
class EncodedMatchResult:
    matches: tuple[EncodedMatch, ...]
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

    def match_encoded(
        self,
        parts: Sequence[bytes | str],
        *,
        max_candidates: int = 256,
        max_depth: int = 4,
        max_work_bytes: int | None = None,
    ) -> EncodedMatchResult:
        """Inspect bounded representations without joining independent input fields.

        Decode percent escapes, JSON string values, and whole-candidate standard or
        URL-safe base64, including JSON/form fields. Arbitrary transformations and
        markers split across fields are outside this boundary. A failed bound raises;
        callers must report incomplete coverage, never a successful clean scan.
        """
        if type(max_candidates) is not int or not 1 <= max_candidates <= 1024:
            raise ValueError("max_candidates must be between 1 and 1024")
        if type(max_depth) is not int or not 0 <= max_depth <= 8:
            raise ValueError("max_depth must be between 0 and 8")
        work_limit = self.max_bytes * 8 if max_work_bytes is None else max_work_bytes
        if type(work_limit) is not int or not 1 <= work_limit <= 128 * DEFAULT_MAX_BYTES:
            raise ValueError("max_work_bytes must be between 1 byte and 128 MiB")
        queue: deque[tuple[bytes, str, int]] = deque()
        seen: set[bytes] = set()
        total_input = 0
        work = 0

        def enqueue(data: bytes, encoding: str, depth: int) -> None:
            nonlocal work
            if not data or data in seen:
                return
            if depth > max_depth:
                raise DecodeError("decode_depth")
            if len(seen) >= max_candidates:
                raise DecodeError("decode_candidates")
            if work + len(data) > work_limit:
                raise DecodeError("decode_bytes")
            work += len(data)
            seen.add(data)
            queue.append((data, encoding, depth))

        if len(parts) > max_candidates:
            raise DecodeError("decode_candidates")
        for part in parts:
            data = bounded_bytes(part, self.max_bytes)
            total_input += len(data)
            if total_input > self.max_bytes:
                raise PayloadTooLarge("input fields exceed observation byte limit")
            enqueue(data, "plaintext", 0)
        found: dict[str, EncodedMatch] = {}
        while queue:
            data, encoding, depth = queue.popleft()
            for canary in self.match(data).canaries:
                found.setdefault(canary.id, EncodedMatch(canary, encoding))
            if re.search(rb"%[0-9A-Fa-f]{2}", data):
                enqueue(unquote_to_bytes(data), "percent", depth + 1)
            stripped = data.strip()
            if stripped[:1] in (b"{", b"[", b'"'):
                try:
                    value = json.loads(stripped)
                except (ValueError, RecursionError):
                    raise DecodeError("invalid_json") from None
                nodes = [value]
                visited = 0
                while nodes:
                    visited += 1
                    if visited > max_candidates:
                        raise DecodeError("json_nodes")
                    node = nodes.pop()
                    if isinstance(node, str):
                        try:
                            decoded = node.encode("utf-8")
                        except UnicodeError:
                            raise DecodeError("invalid_json_unicode") from None
                        enqueue(decoded, "json", depth + 1)
                    elif isinstance(node, (list, dict)):
                        children = (
                            [*node.keys(), *node.values()] if isinstance(node, dict) else node
                        )
                        if len(nodes) + len(children) + visited > max_candidates:
                            raise DecodeError("json_nodes")
                        nodes.extend(children)
            if len(stripped) >= 24 and re.fullmatch(rb"[A-Za-z0-9_+/-]+={0,2}", stripped):
                try:
                    decoded = base64.b64decode(
                        stripped + b"=" * (-len(stripped) % 4), altchars=b"-_", validate=True
                    )
                except (ValueError, binascii.Error):
                    pass
                else:
                    enqueue(decoded, "base64", depth + 1)
            # Common URL-form encoded fields only; matches remain field-local.
            for field in re.finditer(
                rb"(?:^|[?&])(?:data|payload|content|input|body|base64|encoded)=([^&]*)", data
            ):
                enqueue(field[1], "form", depth + 1)
        return EncodedMatchResult(tuple(found.values()), work)
