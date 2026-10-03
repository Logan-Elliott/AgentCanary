"""Explicit HTTP observation without upstream I/O or request-content persistence."""

from __future__ import annotations

import ipaddress
import os
import re
import threading
import zlib
from collections.abc import Mapping, Sequence
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from .matching import DEFAULT_MAX_BYTES, DecodeError, PayloadTooLarge, TokenMatcher, bounded_bytes
from .models import TOKEN_PATTERN, Action, Event, Scalar
from .protocols import EventSink
from .store import Store

Headers = Mapping[str, str] | Sequence[tuple[str, str]]
MODEL_ROUTES = frozenset(
    f"{prefix}/{route}"
    for prefix in ("", "/v1")
    for route in ("chat/completions", "completions", "responses", "messages", "embeddings")
)


def safe_origin(url: str) -> str:
    """Canonical HTTP(S) origin only. Parsing never performs DNS or socket I/O."""
    try:
        if len(url) > 16384 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            raise ValueError
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
        if parsed.scheme not in ("http", "https") or not host:
            raise ValueError
        host = re.sub(TOKEN_PATTERN.pattern, "redacted", host, flags=re.IGNORECASE)
        if ":" in host:
            host = f"[{ipaddress.IPv6Address(host).compressed}]"
        elif re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?", host) is None:
            raise ValueError
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        suffix = (
            f":{port}"
            if port is not None and port != (443 if parsed.scheme == "https" else 80)
            else ""
        )
        return f"{parsed.scheme}://{host.lower()}{suffix}"
    except ValueError:
        raise ValueError("destination must contain a valid HTTP(S) origin") from None


def model_route(target: str) -> str | None:
    try:
        path = unquote(urlsplit(target).path).rstrip("/")
    except ValueError:
        return None
    return path if path in MODEL_ROUTES else None


def _body_bytes(body: bytes | str, encoding: str | None, limit: int) -> bytes:
    data = bounded_bytes(body, limit)
    if encoding is None or encoding.strip().lower() in ("", "identity"):
        return data
    if encoding.strip().lower() != "gzip":
        raise DecodeError("unsupported_content_encoding")
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        decoded = decoder.decompress(data, limit + 1)
        if len(decoded) > limit or decoder.unconsumed_tail:
            raise DecodeError("gzip_limit")
        if not decoder.eof or decoder.unused_data:
            raise DecodeError("invalid_gzip")
        return decoded
    except zlib.error:
        raise DecodeError("invalid_gzip") from None


class HTTPInspector:
    """Registry snapshot for HTTP fields or explicit model input; never sends data.

    Default source=http has no client PID. SDK mode identifies this calling process.
    refresh() updates the registry snapshot explicitly, as in Observer.
    """

    def __init__(
        self,
        store: Store,
        *,
        sink: EventSink | None = None,
        run_id: str | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        source: str = "http",
        matcher: TokenMatcher | None = None,
    ) -> None:
        if source not in ("http", "sdk"):
            raise ValueError("HTTP inspection source must be http or sdk")
        self.store = store
        self.sink = store if sink is None else sink
        self.run_id = str(uuid4()) if run_id is None else run_id
        self.source = source
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._matcher = matcher or TokenMatcher(store.canaries(), max_bytes=max_bytes)
        Event(action=Action.MONITOR_HEALTH, source=source, run_id=self.run_id)

    def refresh(self) -> None:
        matcher = TokenMatcher(self.store.canaries(), max_bytes=self.max_bytes)
        with self._lock:
            self._matcher = matcher

    def health(self, reason: str) -> Event:
        return self.sink.record(
            Event(
                action=Action.MONITOR_HEALTH,
                source=self.source,
                provenance=f"{self.source}_diagnostic",
                run_id=self.run_id,
                pid=os.getpid() if self.source == "sdk" else None,
                metadata={"healthy": False, "reason": reason, "operation": "http_inspection"},
            )
        )

    def _events(
        self,
        parts: Sequence[bytes | str],
        actions: Sequence[Action],
        destination: str,
        metadata: dict[str, Scalar],
        provenance: str,
    ) -> tuple[Event, ...]:
        with self._lock:
            matcher = self._matcher
        try:
            result = matcher.match_encoded(parts)
        except (DecodeError, PayloadTooLarge) as exc:
            self.health(exc.reason if isinstance(exc, DecodeError) else "payload_limit")
            raise
        metadata.update(
            attribution="caller_pid" if self.source == "sdk" else "unknown_client",
            bytes_scanned=result.bytes_scanned,
            match_count=len(result.matches),
        )
        return tuple(
            self.sink.record(
                Event(
                    action=action,
                    source=self.source,
                    canary_id=match.canary.id,
                    provenance=provenance,
                    run_id=self.run_id,
                    pid=os.getpid() if self.source == "sdk" else None,
                    destination=destination,
                    metadata=dict(metadata, matched_encoding=match.encoding),
                )
            )
            for match in result.matches
            for action in actions
        )

    def inspect(
        self,
        method: str,
        target: str,
        *,
        headers: Headers = (),
        body: bytes | str = b"",
        blocked: bool = False,
    ) -> tuple[Event, ...]:
        """Observe complete bounded HTTP input; blocked=True is reserved for a blocking adapter."""
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            self.health("unsupported_method")
            raise ValueError("unsupported HTTP method")
        pairs = list(headers.items()) if isinstance(headers, Mapping) else list(headers)
        if len(pairs) > 64:
            self.health("header_limit")
            raise PayloadTooLarge("HTTP header limit exceeded")
        lowered: dict[str, str] = {}
        for name, value in pairs:
            key = name.lower()
            if key in lowered and key in (
                "host",
                "content-length",
                "content-encoding",
                "transfer-encoding",
            ):
                self.health("ambiguous_headers")
                raise ValueError("ambiguous HTTP headers")
            lowered[key] = value
        if "transfer-encoding" in lowered:
            self.health("unsupported_transfer_encoding")
            raise ValueError("unsupported HTTP transfer encoding")
        try:
            target = bounded_bytes(target, min(self.max_bytes, 16384)).decode("utf-8")
            if target.startswith("/") and not target.startswith("//"):
                destination = safe_origin("http://" + lowered.get("host", "localhost"))
            else:
                destination = safe_origin(target)
            data = _body_bytes(body, lowered.get("content-encoding"), self.max_bytes)
        except (DecodeError, PayloadTooLarge, ValueError) as exc:
            reason = exc.reason if isinstance(exc, DecodeError) else "invalid_http_input"
            self.health(reason)
            raise
        route = model_route(target)
        actions = [Action.EXFILTRATION]
        metadata: dict[str, Scalar] = {
            "method": method,
            "blocked": blocked,
            "operation": "transmission_attempt" if blocked else "input_observed",
            "body_bytes": len(data),
        }
        if route is not None:
            actions.append(Action.MODEL_REQUEST)
            metadata["route"] = route
        if lowered.get("content-encoding", "").strip().lower() == "gzip":
            metadata["content_encoding"] = "gzip"
        parts: list[bytes | str] = [target, data]
        parts.extend(item for pair in pairs for item in pair)
        return self._events(
            parts,
            actions,
            destination,
            metadata,
            "http_request_blocked" if blocked else f"{self.source}_http_input",
        )

    def inspect_model(
        self,
        payload: bytes | str,
        *,
        destination: str,
        embedding: bool = False,
    ) -> tuple[Event, ...]:
        """Observe explicit model or embedding input; no delivery or semantic-use claim."""
        origin = safe_origin(destination)
        metadata: dict[str, Scalar] = {
            "operation": "embedding_input" if embedding else "model_input",
        }
        route = model_route(destination)
        if route is not None:
            metadata["route"] = route
        return self._events(
            [payload], [Action.MODEL_REQUEST], origin, metadata, f"{self.source}_model_input"
        )
