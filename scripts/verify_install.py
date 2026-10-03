"""Build-artifact checks and clean installed CLI/demo verification, using only stdlib.

Run after `uv build`. Source installation may download isolated build dependencies;
all application checks use temporary local fixtures and loopback connections.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from email.parser import Parser
from pathlib import Path

LIFECYCLE = {"CREATE", "READ", "COPY", "TOOL_USE", "MODEL_REQUEST", "EXFILTRATION"}


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def inspect_artifacts(wheel: Path, source: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for expected in ("agentcanary/py.typed", "agentcanary/demo.py", "agentcanary/__main__.py"):
            require(expected in names, f"wheel lacks {expected}")
        metadata_file = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_file).decode())
        require(metadata["Name"] == "agentcanary", "unexpected wheel package name")
        require(metadata["License-Expression"] == "MIT", "missing SPDX license metadata")
        require(not metadata.get_all("Requires-Dist"), "unexpected runtime dependency")
        require(any(name.endswith("/licenses/LICENSE") for name in names), "wheel lacks license")
    with tarfile.open(source) as archive:
        names = archive.getnames()
    relative = {name.partition("/")[2] for name in names}
    for expected in (
        "LICENSE",
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "pyproject.toml",
        "uv.lock",
        "src/agentcanary/py.typed",
        "src/agentcanary/demo.py",
        "docs/architecture.md",
        "docs/threat-model.md",
        "docs/limitations.md",
        "docs/integrations.md",
        "examples/observe_workspace.py",
        "examples/custom-template.txt",
        "examples/policy.toml",
        "tests/test_demo.py",
        "scripts/verify_install.py",
    ):
        require(expected in relative, f"source distribution lacks {expected}")
    forbidden = {".planning", ".claude", ".bg-shell", ".mcp.json", ".venv", ".agentcanary"}
    require(
        not any(forbidden.intersection(Path(name).parts) for name in relative),
        "source distribution includes local development state",
    )


def verify_install(artifact: Path) -> None:
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    with tempfile.TemporaryDirectory(prefix="agentcanary-install-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin" / "python"
        command = environment / "bin" / "agentcanary"
        work = root / "work"
        work.mkdir()

        def run(argv: list[str], *, timeout: float = 60) -> str:
            result = subprocess.run(
                argv,
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
            return result.stdout

        install = [str(python), "-I", "-m", "pip", "install", "--no-input", "--no-deps"]
        if artifact.suffix == ".whl":
            install.append("--no-index")
        run([*install, str(artifact)], timeout=180)
        run([str(python), "-I", "-m", "pip", "check"])
        imported = Path(
            run(
                [str(python), "-I", "-c", "import agentcanary; print(agentcanary.__file__)"]
            ).strip()
        )
        require(imported.is_relative_to(environment), "import escaped the clean environment")
        require("agentcanary" in run([str(command), "--version"]), "version command failed")
        for subcommand in (None, "create", "seed", "monitor", "proxy", "report", "demo"):
            run([str(command), *([subcommand] if subcommand else []), "--help"])

        def cli(*args: str) -> str:
            return run([str(command), "--state-dir", str(work / "state"), *args])

        for kind in ("aws-key", "kubeconfig"):
            created = json.loads(cli("create", kind, "--json"))
            require(len(created) == 1 and created[0]["kind"] == kind, "individual create failed")
        seeded = json.loads(cli("seed", "workspace", "--profile", "realistic", "--json"))
        require(len(seeded) == 8, "realistic profile did not produce eight artifacts")
        monitor = json.loads(cli("monitor", "workspace", "--duration", "0.1"))
        require(monitor["watch_count"] == 8, "installed passive monitor coverage incomplete")
        proxy = json.loads(cli("proxy", "--port", "0", "--duration", "0.1"))
        require(proxy["mode"] == "always_block", "installed proxy readiness failed")
        report = json.loads(cli("report", "--format", "json"))
        require(report["count"] >= 10, "installed creation evidence missing")

        summary_text = cli("demo", "--directory", str(work / "demo"), "--json")
        summary = json.loads(summary_text)
        require(summary["status"] == "complete", "installed demo did not complete")
        require(set(summary["actions"]) == LIFECYCLE, "installed demo chain incomplete")
        require(summary["http_statuses"] == [403, 403], "installed demo HTTP was not blocked")
        evidence = run(
            [str(command), "--state-dir", summary["state_dir"], "report", "--format", "json"]
        )
        events = json.loads(evidence)["events"]
        require({event["action"] for event in events} >= LIFECYCLE, "installed report lost chain")
        require(
            "AGENTCANARY_SYNTHETIC_" not in evidence + summary_text,
            "installed report exposed a synthetic marker",
        )
        exported = [
            json.loads(line) for line in (work / "demo" / "events.jsonl").read_text().splitlines()
        ]
        require(len(exported) == len(events), "demo export and installed report disagree")
        print(f"PASS {artifact.name}: clean install, CLI, monitor, proxy and complete demo")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    directory = args.dist.resolve()
    wheels, sources = sorted(directory.glob("*.whl")), sorted(directory.glob("*.tar.gz"))
    require(len(wheels) == len(sources) == 1, "build exactly one wheel and sdist in --dist first")
    inspect_artifacts(wheels[0], sources[0])
    for artifact in (wheels[0], sources[0]):
        verify_install(artifact)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "", file=sys.stderr)
        print(exc.stderr or "", file=sys.stderr)
        raise SystemExit(f"installation verification command failed ({exc.returncode})") from None
