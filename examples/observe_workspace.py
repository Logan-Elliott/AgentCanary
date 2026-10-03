"""Explicit local SDK observations for an already seeded workspace."""

import argparse
import sys
from pathlib import Path

from agentcanary import Observer, Store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(".agentcanary"))
    args = parser.parse_args()
    observer = Observer(Store(args.state_dir), run_id="sdk-example")
    payload = observer.read(args.workspace / ".aws" / "credentials")
    result = observer.run_tool(
        [sys.executable, "-c", "import sys; assert sys.stdin.buffer.read()"],
        input=payload,
        tool="local-fixture",
    )
    observer.observe_model(payload, destination="https://mock-model.invalid/v1/responses")
    print(f"Tool exit: {result.returncode}; inspect agentcanary report --run-id sdk-example")


if __name__ == "__main__":
    main()
