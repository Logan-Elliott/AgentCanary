"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from . import __version__
from .generator import PROFILES, create_canary, seed
from .models import Action
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
    types = commands.add_parser("types", help="list synthetic artifact types and profiles")
    types.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
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
            output = render_report(events, format=args.format, canaries=store.canaries())
            if output:
                print(output)
            return 0
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
    except (OSError, ValueError, StoreError) as exc:
        message = redact_text(str(exc))
        message = "".join(c if ord(c) >= 32 and ord(c) != 127 else "?" for c in message)
        print(f"agentcanary: {message}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("agentcanary: interrupted", file=sys.stderr)
        return 130
