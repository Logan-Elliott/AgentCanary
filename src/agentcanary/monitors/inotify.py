"""Linux inode-access snapshots without PID or byte-consumption inference.

Content is read only before watches are installed. Any change invalidates a watch;
stop/start explicitly refreshes the registry and revalidates files. Access may be
coalesced, mmap is not covered, and startup/shutdown are observation gaps.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import select
import stat
import struct
import sys
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from ..filesystem import UnsafePathError, absolute_path, open_directory
from ..matching import DEFAULT_MAX_BYTES
from ..models import Action, Canary, Event, Scalar
from ..protocols import EventSink
from ..store import Store

IN_ACCESS = 0x00000001
IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_UNMOUNT = 0x00002000
IN_Q_OVERFLOW = 0x00004000
IN_IGNORED = 0x00008000
_INVALID = IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | IN_DELETE_SELF | IN_MOVE_SELF | IN_UNMOUNT
_HEADER = struct.Struct("iIII")


class MonitorError(RuntimeError):
    """Monitor coverage or lifecycle failed; no artifact content is included."""


class _Inotify:
    def __init__(self) -> None:
        if not sys.platform.startswith("linux"):
            raise MonitorError("inotify monitoring requires Linux")
        self._libc = ctypes.CDLL(None, use_errno=True)
        self._libc.inotify_init1.argtypes = [ctypes.c_int]
        self._libc.inotify_init1.restype = ctypes.c_int
        self._libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self._libc.inotify_add_watch.restype = ctypes.c_int
        self._libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
        self._libc.inotify_rm_watch.restype = ctypes.c_int
        self.fd = int(self._libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC))
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify initialization failed")

    def add(self, file_fd: int) -> int:
        # /proc selects the already validated open inode, eliminating path substitution.
        wd = int(
            self._libc.inotify_add_watch(
                self.fd,
                os.fsencode(f"/proc/self/fd/{file_fd}"),
                IN_ACCESS | _INVALID,
            )
        )
        if wd < 0:
            raise OSError(ctypes.get_errno(), "inotify watch installation failed")
        return wd

    def remove(self, wd: int) -> None:
        self._libc.inotify_rm_watch(self.fd, wd)

    def read(self) -> bytes:
        try:
            return os.read(self.fd, 65536)
        except BlockingIOError:
            return b""

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _version(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_nlink,
        info.st_mode,
    )


def _path_version(path: str) -> tuple[int, ...]:
    value = absolute_path(path)
    parent = open_directory(value.parent)
    try:
        return _version(os.stat(value.name, dir_fd=parent, follow_symlinks=False))
    finally:
        os.close(parent)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    canary: Canary
    version: tuple[int, ...]


class InotifyMonitor:
    """Single-worker snapshot. start() returns ready; stop() joins or raises.

    ready is a threading.Event. check() raises after worker/sink failure. watch_count
    reports remaining coverage. health evidence contains all skipped/lost watches.
    Changed artifacts are never rearmed automatically; use stop()/start(). Passive
    reads identify an unchanged registered inode, not a PID, byte range or intent.
    """

    def __init__(
        self,
        store: Store,
        root: str | Path,
        *,
        run_id: str | None = None,
        sink: EventSink | None = None,
    ) -> None:
        self.store = store
        self.root = absolute_path(root)
        self.run_id = run_id if run_id is not None else str(uuid4())
        self.sink = sink if sink is not None else store
        self.ready = threading.Event()
        self._stop = threading.Event()
        self._lifecycle = threading.Lock()
        self._thread: threading.Thread | None = None
        self._backend: _Inotify | None = None
        self._watches: dict[int, _Snapshot] = {}
        self._total = 0
        self._error: str | None = None
        Event(action=Action.MONITOR_HEALTH, source="inotify", run_id=self.run_id)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def watch_count(self) -> int:
        return len(self._watches)

    @property
    def error(self) -> str | None:
        return self._error

    def check(self) -> None:
        if self._error is not None:
            raise MonitorError(self._error)

    def _health(
        self,
        reason: str,
        *,
        canary_id: str | None = None,
        healthy: bool = False,
        extra: dict[str, Scalar] | None = None,
    ) -> None:
        metadata: dict[str, Scalar] = {
            "backend": "inotify",
            "reason": reason,
            "healthy": healthy,
            "watch_count": self.watch_count,
            "missing_count": self._total - self.watch_count,
        }
        metadata.update(extra or {})
        self.sink.record(
            Event(
                action=Action.MONITOR_HEALTH,
                source="inotify",
                provenance="monitor_diagnostic",
                canary_id=canary_id,
                run_id=self.run_id,
                pid=None,
                metadata=metadata,
            )
        )

    def _snapshot(self, canary: Canary) -> tuple[int, _Snapshot]:
        path = absolute_path(canary.path)
        parent = open_directory(path.parent)
        try:
            fd = os.open(
                path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent
            )
        finally:
            os.close(parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise UnsafePathError("snapshot must be a singly linked regular file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(DEFAULT_MAX_BYTES + 1)
            after = os.fstat(fd)
            if (
                len(data) > DEFAULT_MAX_BYTES
                or hashlib.sha256(data).hexdigest() != canary.sha256
                or canary.token.encode("ascii") not in data
            ):
                raise ValueError("altered_file")
            if _version(before) != _version(after):
                raise ValueError("changed_during_snapshot")
            return fd, _Snapshot(canary, _version(after))
        except BaseException:
            os.close(fd)
            raise

    def start(self) -> None:
        with self._lifecycle:
            if self.running:
                raise MonitorError("monitor is already running")
            self._stop.clear()
            self.ready.clear()
            self._error = None
            self._watches.clear()
            pending: list[tuple[int, _Snapshot]] = []
            try:
                root_fd = open_directory(self.root)
                os.close(root_fd)
                self._backend = _Inotify()
                canaries = self.store.canaries()
                self._total = len(canaries)
                for canary in canaries:
                    if not absolute_path(canary.path).is_relative_to(self.root):
                        self._health("outside_root", canary_id=canary.id)
                        continue
                    try:
                        pending.append(self._snapshot(canary))
                    except FileNotFoundError:
                        self._health("missing_file", canary_id=canary.id)
                    except UnsafePathError:
                        self._health("unsafe_file", canary_id=canary.id)
                    except ValueError:
                        self._health("altered_file", canary_id=canary.id)
                    except OSError:
                        self._health("unavailable_file", canary_id=canary.id)
                # All validation reads precede every watch: no monitor feedback loop.
                for fd, snapshot in pending:
                    wd = self._backend.add(fd)
                    if wd in self._watches:
                        # inotify reuses a descriptor for the same inode. Keep
                        # the original coverage instead of silently replacing it.
                        self._health("duplicate_inode", canary_id=snapshot.canary.id)
                        continue
                    self._watches[wd] = snapshot
                    if _version(os.fstat(fd)) != snapshot.version or not self._current(snapshot):
                        self._invalidate(wd, "changed_during_start")
                self._health(
                    "snapshot_started" if self._total else "empty_registry",
                    healthy=self.watch_count == self._total and self._total > 0,
                )
                self._thread = threading.Thread(
                    target=self._run, name="agentcanary-inotify", daemon=True
                )
                self._thread.start()
                if not self.ready.wait(5):
                    self._stop.set()
                    raise MonitorError("monitor readiness timed out")
                self.check()
            except BaseException as exc:
                self._stop.set()
                if self.running and self._thread is not None:
                    self._thread.join(10)
                if not self.running:
                    self._close()
                    self._thread = None
                    self.ready.clear()
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    with suppress(Exception):
                        self._health("startup_interrupted")
                    raise
                self._error = self._error or (
                    "monitor startup failed"
                    if sys.platform.startswith("linux")
                    else "inotify monitoring requires Linux"
                )
                with suppress(Exception):
                    self._health("startup_failed")
                raise MonitorError(self._error) from None
            finally:
                for fd, _ in pending:
                    os.close(fd)

    def _current(self, snapshot: _Snapshot) -> bool:
        try:
            return _path_version(snapshot.canary.path) == snapshot.version
        except (OSError, ValueError):
            return False

    def _invalidate(self, wd: int, reason: str) -> None:
        snapshot = self._watches.pop(wd, None)
        if snapshot is not None:
            if self._backend is not None:
                self._backend.remove(wd)
            self._health(reason, canary_id=snapshot.canary.id)

    def _process(self, data: bytes) -> None:
        events: list[tuple[int, int]] = []
        offset = 0
        while offset < len(data):
            if offset + _HEADER.size > len(data):
                raise MonitorError("truncated inotify event")
            wd, mask, _, length = _HEADER.unpack_from(data, offset)
            offset += _HEADER.size + length
            if offset > len(data):
                raise MonitorError("truncated inotify name")
            events.append((wd, mask))
        # An overflow destroys snapshot continuity. No queued access can be trusted.
        if any(mask & IN_Q_OVERFLOW for _, mask in events):
            if self._backend is not None:
                for wd in self._watches:
                    self._backend.remove(wd)
            self._watches.clear()
            self._health("queue_overflow", extra={"dropped_events": -1})
            return
        # Conservatively discard accesses in the same batch as invalidation.
        for wd, mask in events:
            if mask & (_INVALID | IN_IGNORED):
                self._invalidate(wd, "coverage_lost")
        for wd, mask in events:
            if self._stop.is_set():
                return
            snapshot = self._watches.get(wd)
            if snapshot is None or not mask & IN_ACCESS:
                continue
            if not self._current(snapshot):
                self._invalidate(wd, "coverage_lost")
                continue
            self.sink.record(
                Event(
                    action=Action.READ,
                    source="inotify",
                    provenance="kernel_inode_access",
                    canary_id=snapshot.canary.id,
                    run_id=self.run_id,
                    pid=None,
                    metadata={
                        "backend": "inotify",
                        "attribution": "unknown",
                        "confidence": "validated_inode_access",
                        "mask": mask,
                    },
                )
            )

    def _close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None
        self._watches.clear()

    def _run(self) -> None:
        self.ready.set()
        try:
            backend = self._backend
            if backend is None:
                raise MonitorError("monitor backend missing")
            while not self._stop.is_set():
                if select.select([backend.fd], [], [], 0.1)[0]:
                    self._process(backend.read())
                # Metadata-only identity checks catch ancestor rename/replacement too.
                for wd, snapshot in tuple(self._watches.items()):
                    if self._stop.is_set():
                        break
                    if not self._current(snapshot):
                        self._invalidate(wd, "coverage_lost")
        except BaseException as exc:
            self._error = f"monitor worker failed ({type(exc).__name__})"
            with suppress(Exception):
                self._health("worker_failed", extra={"error_code": type(exc).__name__})
        finally:
            self._close()

    def stop(self) -> None:
        with self._lifecycle:
            thread = self._thread
            if thread is None:
                self.check()
                return
            self._stop.set()
            thread.join(10)
            if thread.is_alive():
                self._error = "monitor worker did not stop within 10 seconds"
                raise MonitorError(self._error)
            self._thread = None
            self.check()
            self._health("stopped")

    def __enter__(self) -> InotifyMonitor:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
