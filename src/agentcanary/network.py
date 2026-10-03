"""Explicit HTTP observation without upstream I/O or request-content persistence."""

from __future__ import annotations

import ipaddress
import math
import os
import re
import socket
import threading
import time
import zlib
from collections.abc import Mapping, Sequence
from contextlib import suppress
from types import TracebackType
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
        return self._record(
            Event(
                action=Action.MONITOR_HEALTH,
                source=self.source,
                provenance=f"{self.source}_diagnostic",
                run_id=self.run_id,
                pid=os.getpid() if self.source == "sdk" else None,
                metadata={"healthy": False, "reason": reason, "operation": "http_inspection"},
            )
        )

    def _record(self, event: Event) -> Event:
        try:
            return self.sink.record(event)
        except Exception:
            raise NetworkError("HTTP event sink failed") from None

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
            self._record(
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


class NetworkError(RuntimeError):
    """The local listener failed; message deliberately contains no request or sink text."""


class _Rejected(Exception):
    def __init__(self, reason: str, status: int = 400) -> None:
        self.reason = reason
        self.status = status


class BlockingProxy:
    """Bounded loopback HTTP/1 observation endpoint. Every request is closed and blocked.

    No forwarding path, DNS lookup, TLS interception or client-PID attribution exists.
    Only one request is processed per connection. Registry is refreshed on start;
    inspector.refresh() can explicitly update it while running.
    """

    def __init__(
        self,
        store: Store,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        sink: EventSink | None = None,
        run_id: str | None = None,
        max_body_bytes: int = DEFAULT_MAX_BYTES,
        max_header_bytes: int = 32768,
        max_workers: int = 8,
        read_timeout: float = 5.0,
    ) -> None:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError("listener requires a numeric loopback address") from None
        if not address.is_loopback or "%" in host:
            raise ValueError("listener requires a numeric loopback address")
        for value, low, high, name in (
            (port, 0, 65535, "port"),
            (max_body_bytes, 1, 16 * DEFAULT_MAX_BYTES, "max_body_bytes"),
            (max_header_bytes, 128, 65536, "max_header_bytes"),
            (max_workers, 1, 64, "max_workers"),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} is outside the supported bound")
        if not math.isfinite(read_timeout) or not 0.05 <= read_timeout <= 60:
            raise ValueError("read_timeout must be between 0.05 and 60 seconds")
        self.host = str(address)
        self.port = port
        self._family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        self.max_body_bytes = max_body_bytes
        self.max_header_bytes = max_header_bytes
        self.max_workers = max_workers
        self.read_timeout = read_timeout
        # Reserve additional bounded input space for request target and headers.
        self.inspector = HTTPInspector(
            store,
            sink=sink,
            run_id=run_id,
            max_bytes=min(16 * DEFAULT_MAX_BYTES, max_body_bytes + max_header_bytes + 16384),
        )
        self.run_id = self.inspector.run_id
        self.ready = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_workers)
        self._workers: dict[threading.Thread, socket.socket] = {}
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if self._family == socket.AF_INET6 else self.host
        return f"http://{host}:{self.port}"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stopped.is_set()

    def check(self) -> None:
        if self.error is not None:
            raise NetworkError(f"HTTP listener failed: {self.error}")

    def _fail(self, reason: str) -> None:
        with self._lock:
            if self.error is None:
                self.error = reason
        self.ready.clear()
        self._stopped.set()

    def start(self) -> None:
        if self.running:
            return
        if self._thread is not None:
            raise NetworkError("stop the previous listener before restarting")
        self.error = None
        self._stopped.clear()
        listener = socket.socket(self._family, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.port))
            listener.listen(self.max_workers)
            listener.settimeout(0.1)
            self.inspector.refresh()
            if not self.inspector.store.canaries():
                self.inspector.health("empty_registry")
            self.port = listener.getsockname()[1]
            self._listener = listener
            self._thread = threading.Thread(
                target=self._accept, name="agentcanary-http", daemon=True
            )
            self._thread.start()
            self.ready.set()
        except Exception:
            listener.close()
            self._listener = None
            self._thread = None
            raise NetworkError("HTTP listener startup failed") from None

    def stop(self) -> None:
        self._stopped.set()
        self.ready.clear()
        listener = self._listener
        if listener is not None:
            listener.close()
        with self._lock:
            connections = list(self._workers.values())
        for connection in connections:
            with suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
        deadline = time.monotonic() + 2.0
        if self._thread is not None:
            self._thread.join(max(0.0, deadline - time.monotonic()))
        with self._lock:
            workers = list(self._workers)
        for worker in workers:
            worker.join(max(0.0, deadline - time.monotonic()))
        if any(worker.is_alive() for worker in workers) or (
            self._thread is not None and self._thread.is_alive()
        ):
            self._fail("shutdown_timeout")
        else:
            self._listener = None
            self._thread = None
        self.check()

    def __enter__(self) -> BlockingProxy:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

    @staticmethod
    def _respond(connection: socket.socket, status: int) -> None:
        # Constant body and status text: no parser, header or exception reflection.
        body = b"AgentCanary: request blocked.\n"
        response = (
            f"HTTP/1.1 {status} Blocked\r\nConnection: close\r\n"
            f"Content-Type: text/plain\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode("ascii") + body
        with suppress(OSError):
            connection.settimeout(0.1)
            connection.sendall(response)
            connection.shutdown(socket.SHUT_WR)

    def _accept(self) -> None:
        listener = self._listener
        assert listener is not None
        try:
            while not self._stopped.is_set():
                try:
                    connection, _ = listener.accept()
                except TimeoutError:
                    continue
                if self._stopped.is_set():
                    connection.close()
                    break
                if not self._slots.acquire(blocking=False):
                    self._respond(connection, 503)
                    connection.close()
                    self.inspector.health("worker_limit")
                    continue
                worker = threading.Thread(
                    target=self._handle,
                    args=(connection,),
                    name="agentcanary-http-client",
                    daemon=True,
                )
                try:
                    with self._lock:
                        if self._stopped.is_set():
                            connection.close()
                            self._slots.release()
                            break
                        self._workers[worker] = connection
                        worker.start()
                except Exception:
                    with self._lock:
                        del self._workers[worker]
                    connection.close()
                    self._slots.release()
                    raise
        except Exception:
            if not self._stopped.is_set():
                self._fail("listener_or_sink_failure")
        finally:
            listener.close()

    @staticmethod
    def _receive(connection: socket.socket, size: int, deadline: float) -> bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        connection.settimeout(remaining)
        return connection.recv(size)

    def _request(self, connection: socket.socket) -> tuple[str, str, list[tuple[str, str]], bytes]:
        deadline = time.monotonic() + self.read_timeout
        received = bytearray()
        while b"\r\n\r\n" not in received:
            if len(received) >= self.max_header_bytes:
                raise _Rejected("header_limit", 431)
            chunk = self._receive(
                connection, min(4096, self.max_header_bytes - len(received)), deadline
            )
            if not chunk:
                raise _Rejected("incomplete_headers")
            received.extend(chunk)
        head, body = bytes(received).split(b"\r\n\r\n", 1)
        lines = head.split(b"\r\n")
        if len(lines[0]) > 8192:
            raise _Rejected("request_line_limit", 414)
        if len(lines) > 65:
            raise _Rejected("header_count", 431)
        request_line = re.fullmatch(rb"([A-Z]+) ([\x21-\x7e]+) HTTP/1\.[01]", lines[0])
        if request_line is None:
            raise _Rejected("invalid_request_line")
        method, target = (part.decode("ascii") for part in request_line.groups())
        if method == "CONNECT":
            raise _Rejected("tls_tunnel_unsupported", 501)
        if method not in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            raise _Rejected("unsupported_method", 501)
        if not target.startswith(("/", "http://", "https://")) or target.startswith("//"):
            raise _Rejected("invalid_request_target")
        pairs: list[tuple[str, str]] = []
        headers: dict[str, str] = {}
        for line in lines[1:]:
            name, colon, value = line.partition(b":")
            if not colon or re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) is None:
                raise _Rejected("invalid_header")
            if any(byte < 32 and byte != 9 or byte >= 127 for byte in value):
                raise _Rejected("invalid_header")
            key = name.decode("ascii").lower()
            if key in headers and key in (
                "host",
                "content-length",
                "content-encoding",
                "transfer-encoding",
            ):
                raise _Rejected("ambiguous_headers")
            text = value.decode("ascii").strip(" \t")
            headers[key] = text
            pairs.append((name.decode("ascii"), text))
        if "host" not in headers or not headers["host"]:
            raise _Rejected("missing_host")
        if "transfer-encoding" in headers:
            raise _Rejected("unsupported_transfer_encoding", 501)
        if "expect" in headers:
            raise _Rejected("unsupported_expectation", 417)
        length = headers.get("content-length", "0")
        if re.fullmatch(r"[0-9]{1,10}", length) is None:
            raise _Rejected("invalid_content_length")
        size = int(length)
        if size > self.max_body_bytes:
            raise _Rejected("body_limit", 413)
        if len(body) > size:
            raise _Rejected("unexpected_trailing_data")
        chunks = bytearray(body)
        while len(chunks) < size:
            chunk = self._receive(connection, min(65536, size - len(chunks)), deadline)
            if not chunk:
                raise _Rejected("incomplete_body")
            chunks.extend(chunk)
        return method, target, pairs, bytes(chunks)

    def _handle(self, connection: socket.socket) -> None:
        try:
            try:
                method, target, headers, body = self._request(connection)
                # Expansion obeys the body bound independently of header budget.
                encoding = next((v for k, v in headers if k.lower() == "content-encoding"), None)
                _body_bytes(body, encoding, self.max_body_bytes)
                self.inspector.inspect(method, target, headers=headers, body=body, blocked=True)
                status = 403
            except _Rejected as exc:
                if not self._stopped.is_set():
                    self.inspector.health(exc.reason)
                status = exc.status
            except TimeoutError:
                if not self._stopped.is_set():
                    self.inspector.health("read_timeout")
                status = 408
            except (DecodeError, PayloadTooLarge) as exc:
                # Inspector reports decoding failures; early gzip bound needs its own diagnostic.
                if isinstance(exc, DecodeError) and exc.reason in (
                    "gzip_limit",
                    "invalid_gzip",
                    "unsupported_content_encoding",
                ):
                    self.inspector.health(exc.reason)
                status = (
                    413
                    if isinstance(exc, PayloadTooLarge) or str(exc).endswith("gzip_limit")
                    else 400
                )
            except ValueError:
                status = 400
            except OSError:
                if not self._stopped.is_set():
                    self.inspector.health("connection_failed")
                status = 400
            self._respond(connection, status)
        except Exception:
            self._fail("event_sink_or_worker_failure")
            self._respond(connection, 500)
        finally:
            connection.close()
            with self._lock:
                self._workers.pop(threading.current_thread(), None)
            self._slots.release()
