"""Explicit cooperative observations; attribution identifies this caller, not intent."""

from __future__ import annotations

import math
import os
import re
import stat
import subprocess
import threading
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .filesystem import UnsafePathError, absolute_path, open_directory
from .matching import DEFAULT_MAX_BYTES, PayloadTooLarge, TokenMatcher, bounded_bytes
from .models import TOKEN_PATTERN, Action, Event, Scalar
from .network import Headers, HTTPInspector
from .policy import Policy, PolicySink
from .protocols import EventSink
from .store import Store


def _safe_path(path: Path) -> str:
    return TOKEN_PATTERN.sub("[canary]", str(path))


def _read_file(path: str | Path, limit: int) -> bytes:
    absolute = absolute_path(path)
    parent = open_directory(absolute.parent)
    try:
        fd = os.open(
            absolute.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=parent,
        )
    finally:
        os.close(parent)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise UnsafePathError("observed input must be a regular file")
        return bounded_bytes(stream.read(limit + 1), limit)


@dataclass(frozen=True, slots=True)
class ToolResult:
    returncode: int
    events: tuple[Event, ...]


class ToolInvocationError(RuntimeError):
    """Invocation failed; arguments and subprocess input are deliberately omitted."""


class Observer:
    """Registry snapshot with explicit refresh(); successful methods surface sink errors.

    read() returns the bytes read. copy() returns COPY events after an exclusive write.
    observe() and observe_tool() describe supplied input, never semantic use.
    run_tool() records invocation attempts before spawning, and discards tool output.
    """

    def __init__(
        self,
        store: Store,
        *,
        run_id: str | None = None,
        sink: EventSink | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        policy: Policy | None = None,
    ) -> None:
        self.store = store
        selected_sink = sink if sink is not None else store
        self.sink: EventSink = (
            PolicySink(selected_sink, policy) if policy is not None else selected_sink
        )
        self.run_id = run_id if run_id is not None else str(uuid4())
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._matcher = TokenMatcher(store.canaries(), max_bytes=max_bytes)
        # Validate labels before performing observable operations.
        Event(action=Action.MONITOR_HEALTH, source="sdk", run_id=self.run_id)

    def refresh(self) -> None:
        matcher = TokenMatcher(self.store.canaries(), max_bytes=self.max_bytes)
        with self._lock:
            self._matcher = matcher

    def _http_inspector(self) -> HTTPInspector:
        with self._lock:
            matcher = self._matcher
        return HTTPInspector(
            self.store,
            sink=self.sink,
            run_id=self.run_id,
            max_bytes=self.max_bytes,
            source="sdk",
            matcher=matcher,
        )

    def observe_http(
        self, method: str, url: str, *, headers: Headers = (), body: bytes | str = b""
    ) -> tuple[Event, ...]:
        """Inspect explicit pre-TLS HTTP input without sending it."""
        return self._http_inspector().inspect(method, url, headers=headers, body=body)

    def observe_model(self, payload: bytes | str, *, destination: str) -> tuple[Event, ...]:
        """Inspect supplied model input before TLS, with caller PID."""
        return self._http_inspector().inspect_model(payload, destination=destination)

    def observe_embedding(self, payload: bytes | str, *, destination: str) -> tuple[Event, ...]:
        """Inspect embedding input before TLS, with caller PID."""
        return self._http_inspector().inspect_model(
            payload, destination=destination, embedding=True
        )

    def _health(self, reason: str, operation: str) -> None:
        self.sink.record(
            Event(
                action=Action.MONITOR_HEALTH,
                source="sdk",
                provenance="sdk_diagnostic",
                pid=os.getpid(),
                run_id=self.run_id,
                metadata={"healthy": False, "reason": reason, "operation": operation},
            )
        )

    def observe(
        self,
        action: Action,
        payload: bytes | str,
        *,
        destination: str | None = None,
        metadata: Mapping[str, Scalar] | None = None,
        provenance: str = "sdk_input",
    ) -> tuple[Event, ...]:
        if not isinstance(action, Action) or action in (Action.CREATE, Action.MONITOR_HEALTH):
            raise ValueError("observe requires an observation Action")
        evidence: dict[str, Scalar] = dict(metadata or {})
        evidence["attribution"] = "caller_pid"
        # Validate even when no markers match, before any events are persisted.
        sanitized = TOKEN_PATTERN.sub("[canary]", destination) if destination else destination
        Event(
            action=Action.MONITOR_HEALTH,
            source="sdk",
            run_id=self.run_id,
            destination=sanitized,
            provenance=provenance,
            metadata=evidence,
        )
        with self._lock:
            matcher = self._matcher
        try:
            result = matcher.match(payload)
        except PayloadTooLarge:
            self._health("payload_limit", action.value)
            raise
        evidence.update(bytes_scanned=result.bytes_scanned, match_count=len(result.canaries))
        return tuple(
            self.sink.record(
                Event(
                    action=action,
                    source="sdk",
                    provenance=provenance,
                    canary_id=canary.id,
                    run_id=self.run_id,
                    pid=os.getpid(),
                    destination=sanitized,
                    metadata=evidence,
                )
            )
            for canary in result.canaries
        )

    def read(self, path: str | Path) -> bytes:
        try:
            data = _read_file(path, self.max_bytes)
        except PayloadTooLarge:
            self._health("payload_limit", "read")
            raise
        self.observe(
            Action.READ,
            data,
            destination=_safe_path(absolute_path(path)),
            provenance="sdk_read_completed",
            metadata={"operation": "read_completed"},
        )
        return data

    def copy(self, source: str | Path, destination: str | Path) -> tuple[Event, ...]:
        try:
            data = _read_file(source, self.max_bytes)
        except PayloadTooLarge:
            self._health("payload_limit", "copy")
            raise
        target = absolute_path(destination)
        # Validate path evidence before the write, including control/length restrictions.
        Event(action=Action.MONITOR_HEALTH, source="sdk", destination=_safe_path(target))
        parent = open_directory(target.parent)
        fd = -1
        try:
            fd = os.open(
                target.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=parent,
            )
            identity = os.fstat(fd)
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(fd)
                os.fsync(parent)
            except BaseException:
                # Never remove a different file substituted during error recovery.
                with suppress(OSError):
                    current = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                        os.unlink(target.name, dir_fd=parent)
                raise
        finally:
            if fd >= 0:
                os.close(fd)
            os.close(parent)
        return self.observe(
            Action.COPY,
            data,
            destination=_safe_path(target),
            provenance="sdk_copy_completed",
            metadata={"operation": "copy_completed", "bytes": len(data)},
        )

    @staticmethod
    def _tool_label(tool: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", tool) is None:
            raise ValueError("tool must be a short identifier")
        return tool

    def observe_tool(self, payload: bytes | str, *, tool: str) -> tuple[Event, ...]:
        return self.observe(
            Action.TOOL_USE,
            payload,
            provenance="sdk_tool_input",
            metadata={"tool": self._tool_label(tool), "operation": "input_observed"},
        )

    def run_tool(
        self,
        argv: Sequence[str],
        *,
        input: bytes | str | None = None,
        tool: str = "subprocess",
        timeout: float = 30.0,
    ) -> ToolResult:
        label = self._tool_label(tool)
        if isinstance(argv, (str, bytes)):
            raise ValueError("argv must be a nonempty sequence of argument strings")
        arguments = tuple(argv)
        if (
            not arguments
            or not all(isinstance(arg, str) and "\0" not in arg for arg in arguments)
            or not arguments[0]
        ):
            raise ValueError("argv must be a nonempty sequence of argument strings")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        try:
            data = bounded_bytes(input if input is not None else b"", self.max_bytes)
            # Bound total argv before joining/encoding; separators prevent cross-argument matches.
            if sum(len(arg) + 1 for arg in arguments) + len(data) > self.max_bytes:
                raise PayloadTooLarge("tool input exceeds observation byte limit")
            payload = bounded_bytes("\0".join(arguments), self.max_bytes) + b"\0" + data
            events = self.observe(
                Action.TOOL_USE,
                payload,
                provenance="sdk_tool_invocation_input",
                metadata={"tool": label, "operation": "invocation_attempt"},
            )
        except PayloadTooLarge:
            self._health("payload_limit", "tool")
            raise
        try:
            result = subprocess.run(
                list(arguments),
                input=data,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            self._health("tool_failed", "invocation")
            raise ToolInvocationError("tool invocation failed or timed out") from None
        return ToolResult(result.returncode, events)
