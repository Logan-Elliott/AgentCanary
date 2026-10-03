"""Command line entry point."""

import argparse
import json
import math
import signal
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from . import __version__
from .demo import DemoError, describe, run_demo
from .generator import PROFILES, create_canary, seed
from .models import Action
from .monitors import InotifyMonitor, MonitorError
from .network import BlockingProxy, NetworkError
from .policy import Policy, PolicySink, load_policy
from .protocols import EventSink
from .report import redact_text, render_report
from .store import Store, StoreError
from .templates import BUILTINS, MAX_TEMPLATE_BYTES


def _template_file(path: str) -> str:
    # Bounded read; templates are inert operator-supplied text.
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_TEMPLATE_BYTES + 1)
    if len(data) > MAX_TEMPLATE_BYTES:
        raise ValueError("template exceeds 256 KiB")
    return data.decode("utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plant synthetic canaries and inspect local evidence.",
        epilog="Place --state-dir before the command. Artifacts are synthetic and nonfunctional.",
    )
    parser.add_argument("--version", action="version", version=f"agentcanary {__version__}")
    parser.add_argument("--state-dir", default=".agentcanary", help="private local state directory")
    parser.add_argument(
        "--config", help="explicit TOML policy file; annotations never permit forwarding"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create one canary without overwriting a file")
    create.add_argument("kind", choices=[*BUILTINS, "custom"], help="synthetic artifact type")
    create.add_argument(
        "--output", help="path relative to --root (default: canaries/TYPE-RANDOM.txt)"
    )
    create.add_argument("--root", default=".", help="workspace directory")
    create.add_argument("--template", help="plain text template with $token; requires custom type")
    create.add_argument("--run-id", help="correlation label")
    create.add_argument("--json", action="store_true", help="output JSON without token values")
    seeds = commands.add_parser("seed", help="seed a profile after checking every destination")
    seeds.add_argument("root", help="workspace directory")
    seeds.add_argument("--profile", choices=PROFILES, default="minimal")
    seeds.add_argument("--run-id", help="correlation label")
    seeds.add_argument("--json", action="store_true", help="output JSON without token values")
    report = commands.add_parser("report", help="show events in durable ingestion order")
    report.add_argument("--format", choices=("text", "json", "jsonl"), default="text")
    report.add_argument("--canary-id", help="filter by canary UUID")
    report.add_argument("--action", choices=[action.value for action in Action])
    report.add_argument("--run-id", help="filter by correlation label")
    report.add_argument("--after-seq", type=int, default=0, help="show events after this sequence")
    report.add_argument("--limit", type=int, help="maximum number of events")
    report.add_argument(
        "--hide-policy",
        action="store_true",
        help="hide ignored/allowlisted observations; retain audit storage",
    )
    monitor = commands.add_parser("monitor", help="watch a registered artifact snapshot on Linux")
    monitor.add_argument("root", help="workspace directory; seed before starting")
    monitor.add_argument("--run-id", help="correlation label")
    monitor.add_argument("--duration", type=float, help="stop after this many seconds")
    proxy = commands.add_parser(
        "proxy",
        aliases=["serve"],
        help="inspect loopback HTTP attempts; always block, never forward",
    )
    proxy.add_argument("--host", default="127.0.0.1", help="numeric loopback bind address")
    proxy.add_argument(
        "--port", type=int, default=8080, help="local listener port; 0 selects a free port"
    )
    proxy.add_argument(
        "--run-id", help="operator correlation label; client headers cannot override it"
    )
    proxy.add_argument("--duration", type=float, help="stop after this many seconds")
    proxy.add_argument(
        "--read-timeout", type=float, default=5.0, help="total request read deadline"
    )
    proxy.add_argument("--max-workers", type=int, default=8, help="maximum simultaneous requests")
    types = commands.add_parser("types", help="list synthetic artifact types and profiles")
    types.add_argument("--json", action="store_true")
    demo = commands.add_parser("demo", help="run an isolated synthetic lifecycle on loopback")
    demo.add_argument("--directory", help="new output directory (default: unique directory in cwd)")
    demo.add_argument(
        "--timeout", type=float, default=15, help="child/evidence deadline in seconds"
    )
    demo.add_argument("--json", action="store_true", help="output summary without token values")
    return parser


def _monitor(
    store: Store,
    root: str,
    run_id: str | None,
    duration: float | None,
    *,
    sink: EventSink | None = None,
) -> int:
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("duration must be positive and finite")
    stopped = threading.Event()
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda signum, frame: stopped.set())
    try:
        with InotifyMonitor(store, root, run_id=run_id, sink=sink) as monitor:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "watch_count": monitor.watch_count,
                        "run_id": monitor.run_id,
                        "registry_policy": "snapshot_restart",
                    }
                ),
                flush=True,
            )
            deadline = time.monotonic() + duration if duration is not None else None
            while not stopped.wait(0.05):
                monitor.check()
                if deadline is not None and time.monotonic() >= deadline:
                    break
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            if args.config is not None:
                raise ValueError("demo uses its isolated default policy; --config is unsupported")
            result = run_demo(args.directory, timeout=args.timeout)
            print(
                redact_text(json.dumps(result.to_dict(), sort_keys=True))
                if args.json
                else describe(result)
            )
            return 0
        policy = load_policy(args.config) if args.config is not None else Policy()
        if args.command == "types":
            catalog = {"types": [*BUILTINS, "custom"], "profiles": list(PROFILES)}
            if args.json:
                print(json.dumps(catalog, sort_keys=True))
            else:
                print("Canary types: " + ", ".join(catalog["types"]))
                print("Seed profiles: " + ", ".join(catalog["profiles"]))
            return 0
        if args.command == "report":
            store = Store(args.state_dir)
            events = store.events(
                canary_id=args.canary_id,
                action=Action(args.action) if args.action else None,
                run_id=args.run_id,
                after_seq=args.after_seq,
                limit=args.limit,
            )
            output = render_report(
                events, format=args.format, canaries=store.canaries(), hide_policy=args.hide_policy
            )
            if output:
                print(output)
            return 0
        if args.command == "monitor":
            store = Store(args.state_dir)
            return _monitor(
                store, args.root, args.run_id, args.duration, sink=PolicySink(store, policy)
            )
        if args.command in ("proxy", "serve"):
            store = Store(args.state_dir)
            return _proxy(store, args, sink=PolicySink(store, policy))
        if args.command == "create":
            if (args.kind == "custom") != bool(args.template):
                raise ValueError("custom type and --template must be used together")
            template = _template_file(args.template) if args.template else None
            path = args.output or f"canaries/{args.kind}-{uuid4().hex[:12]}.txt"
            records = [
                create_canary(
                    Store(args.state_dir),
                    args.root,
                    path,
                    kind=args.kind,
                    template=template,
                    run_id=args.run_id,
                )
            ]
        else:
            records = seed(
                Store(args.state_dir), args.root, profile=args.profile, run_id=args.run_id
            )
        if args.json:
            print(redact_text(json.dumps([record.to_dict() for record in records], sort_keys=True)))
        else:
            for record in records:
                print(redact_text(f"Created {record.kind}: {record.path} ({record.id})"))
        return 0
    except (OSError, ValueError, StoreError, MonitorError, NetworkError, DemoError) as exc:
        message = redact_text(str(exc))
        message = "".join(c if ord(c) >= 32 and ord(c) != 127 else "?" for c in message)
        print(f"agentcanary: {message}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("agentcanary: interrupted", file=sys.stderr)
        return 130


def _proxy(store: Store, args: argparse.Namespace, *, sink: EventSink | None = None) -> int:
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        raise ValueError("duration must be positive and finite")
    stopped = threading.Event()
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda signum, frame: stopped.set())
    try:
        with BlockingProxy(
            store,
            host=args.host,
            port=args.port,
            run_id=args.run_id,
            read_timeout=args.read_timeout,
            max_workers=args.max_workers,
            sink=sink,
        ) as proxy:
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "url": proxy.url,
                        "run_id": proxy.run_id,
                        "mode": "always_block",
                        "registry_policy": "explicit_refresh",
                    }
                ),
                flush=True,
            )
            deadline = time.monotonic() + args.duration if args.duration is not None else None
            while not stopped.wait(0.05):
                proxy.check()
                if deadline is not None and time.monotonic() >= deadline:
                    break
    finally:
        signal.signal(signal.SIGTERM, previous)
    return 0
