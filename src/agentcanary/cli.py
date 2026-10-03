"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .generator import PROFILES, create_canary, seed
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
    create.add_argument("path", help="artifact path relative to --root")
    create.add_argument("--root", default=".", help="workspace directory")
    create.add_argument("--type", choices=[*BUILTINS, "custom"], default="env", dest="kind")
    create.add_argument(
        "--template", help="plain text template with $token; requires --type custom"
    )
    create.add_argument("--run-id", help="correlation label")
    create.add_argument("--json", action="store_true", help="output JSON without token values")
    seeds = commands.add_parser("seed", help="seed a profile after checking every destination")
    seeds.add_argument("root", help="workspace directory")
    seeds.add_argument("--profile", choices=PROFILES, default="minimal")
    seeds.add_argument("--run-id", help="correlation label")
    seeds.add_argument("--json", action="store_true", help="output JSON without token values")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            if (args.kind == "custom") != bool(args.template):
                raise ValueError("--type custom and --template must be used together")
            template = _template_file(args.template) if args.template else None
            records = [
                create_canary(
                    Store(args.state_dir),
                    args.root,
                    args.path,
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
            print(json.dumps([record.to_dict() for record in records], sort_keys=True))
        else:
            for record in records:
                print(f"Created {record.kind}: {record.path} ({record.id})")
        return 0
    except (OSError, ValueError, StoreError) as exc:
        print(f"agentcanary: {exc}", file=sys.stderr)
        return 2
