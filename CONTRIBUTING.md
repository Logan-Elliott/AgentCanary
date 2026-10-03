# Contributing

Use Linux with Python 3.11+ and `/proc` mounted. Install development dependencies with `uv sync --locked`; use the repository lockfile rather than modifying system Python packages.

Before submitting a change:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
uv run python scripts/verify_install.py
```

Keep changes focused and add behavioral tests for safety boundaries or regressions. Tests must use synthetic data, temporary fixtures, local subprocesses and loopback networking. They must not require credentials, root, cloud accounts or external collectors. Use bounded readiness waits rather than fixed sleeps to coordinate integrations.

The installation verifier creates two temporary virtual environments, installs the wheel and source archive separately, and exercises the installed CLI/demo outside the checkout. Build dependencies may be downloaded for source installation. Keep only one version's wheel and source archive in `dist/`, or select another build directory with `--dist`.

The CI definition runs Linux on Python 3.11–3.14, with at most two matrix jobs at once. Reproduce a compatibility run locally without replacing your development environment:

```bash
UV_PROJECT_ENVIRONMENT=.venv-py311 uv sync --locked --python 3.11
.venv-py311/bin/python -m pytest -q
```

New monitors must report source/provenance, unknown attribution, loss conditions and lifecycle failures. New sinks must document ordering, durability and failure semantics. New decoders must bound bytes, recursion and work; unsupported input must not silently appear fully inspected. New templates must remain unmistakably synthetic and nonfunctional.

Do not record real secrets, request bodies, raw tool arguments, environment values or client-controlled identities as trusted event metadata. Preserve existing workspace files and fail explicitly when coverage is incomplete. Update architecture, threat-model and limitation documentation when a change affects those contracts.

Include the problem, resulting behavior and relevant verification in change descriptions. No remote publishing or deployment is part of the local verification workflow.
