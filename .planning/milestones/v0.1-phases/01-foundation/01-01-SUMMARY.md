---
phase: 01-foundation
plan: 01
subsystem: core
tags: [python, sqlite, canaries, filesystem-safety, cli]
requires: []
provides:
  - Eight synthetic canary types and bounded custom text templates
  - Safe batch seeding with no-follow filesystem operations and ordinary-failure rollback
  - Immutable evidence contracts and concurrent durable SQLite registry
  - Installed create/seed/report/types CLI with typed JSON and JSONL reports
affects: [02-observation, 03-network, 04-integration, 05-release]
tech-stack:
  added: [uv, hatchling, pytest, pytest-cov, ruff, mypy, build]
  patterns: [stdlib-only-runtime, frozen-records, per-operation-sqlite-connections, directory-descriptor-writes]
key-files:
  created: [pyproject.toml, uv.lock, src/agentcanary/models.py, src/agentcanary/protocols.py, src/agentcanary/store.py, src/agentcanary/filesystem.py, src/agentcanary/templates.py, src/agentcanary/generator.py, src/agentcanary/cli.py, src/agentcanary/report.py, tests/test_store.py, tests/test_generator.py, tests/test_cli.py, tests/test_concurrency.py, tests/test_report.py]
  modified: [.gitignore]
key-decisions:
  - "Keep runtime dependency-free; use project-local uv dev tools and a committed lockfile."
  - "Store uses short-lived independent SQLite connections, WAL, FULL synchronization and atomic canary/CREATE batches."
  - "Public create CLI accepts the canary type positionally; --output selects a relative path or a unique default is generated."
  - "Reports enrich events with canary_type from the registry; the Event contract retains canary_id as its foreign key."
requirements-completed: [CORE-01, CORE-02, CORE-03, CORE-04]
coverage:
  - id: D1
    description: Unique synthetic nonfunctional artifacts for all eight types
    requirement: CORE-01
    verification:
      - kind: unit
        ref: tests/test_generator.py#test_all_types_are_unique_synthetic_and_correlatable
        status: pass
    human_judgment: false
  - id: D2
    description: Safe profiles and inert custom templates, collision prevention and rollback
    requirement: CORE-02
    verification:
      - kind: integration
        ref: tests/test_generator.py
        status: pass
    human_judgment: false
  - id: D3
    description: Atomic durable evidence with thread and process concurrency
    requirement: CORE-03
    verification:
      - kind: integration
        ref: tests/test_store.py and tests/test_concurrency.py
        status: pass
    human_judgment: false
  - id: D4
    description: Installed CLI, typed extension interfaces and filtered machine-readable reports
    requirement: CORE-04
    verification:
      - kind: integration
        ref: tests/test_cli.py and clean-wheel create/seed/report smoke check
        status: pass
    human_judgment: false
actuals:
  tokens: 43575
  tasks: 3
  commits: 3
commits: 3
plan_head_before: 660352c46df980399827d9d7bf91421eaf033e16
plan_head_after: 7ea2b61f0fd0bac6fddf026e45e7178474203cdc
duration: 24min
completed: 2026-10-03
status: complete
---

# Phase 1 Plan 1: Foundation and safe canary lifecycle Summary

**Synthetic artifacts are safely seeded and paired with durable CREATE evidence, then queried through an installed typed Python package and CLI.**

## Performance

- Started: 2026-10-03T21:19:06Z
- Implementation completed: 2026-10-03T21:42:33Z
- Tasks: 3; code/config/test files changed: 19
- Actual tokens use realized Git diff characters divided by four, including the lockfile.

## Accomplishments

- Added AWS, OpenAI, Anthropic, kubeconfig, SSH, env, database and payroll artifacts with independent 128-bit random markers. Provider-like values are explicitly invalid; SSH material is not a real key and service addresses use `.invalid`.
- Added minimal/realistic profiles, inert `string.Template` custom artifacts, complete destination preflight, `O_EXCL`/`O_NOFOLLOW` creation, private permissions, and ordinary-failure rollback. Tests include a symlink inserted after preflight and a partial write failure.
- Added frozen records, bounded immutable scalar metadata, UUID identifiers, aware UTC timestamps, explicit source/provenance and unknown PID support. SQLite pairs whole canary batches with CREATE records atomically and assigns durable ingestion sequences.
- Added CLI creation by type, profile seeding, discovery, help/version, and filtered text/JSON/JSONL reports with canary types and token redaction.
- Passed 42 tests, Ruff lint/format, strict mypy, wheel/sdist builds and a clean wheel installation smoke check.

## Task Commits

1. Package and immutable evidence contracts — `ff9f33e`
2. Safe templates and seeding — `eab8141`
3. Reports, CLI UX and phase verification — `7ea2b61`

Every commit uses Logan-Elliott <dev.loganelliott@gmail.com>. Existing `.planning/config.json`, `.bg-shell`, `.claude` and `.mcp.json` changes were preserved and excluded from task commits.

## Public API Contracts for Phases 2 and 3

Top-level `agentcanary` exports `Action`, `Canary`, `Event`, `EventSink`, `Monitor`, `Store`, `StoreError`, `SeedSpec`, `GeneratedCanary`, `generate`, `create_canary`, and `seed`. The package carries `py.typed`. Runtime requirements are Python >=3.11 on Linux; the store opens SQLite through `/proc/self/fd` to retain directory identity during operations.

```python
Store(state_dir: str | Path = ".agentcanary")
Store.register(canary: Canary, *, run_id: str | None = None) -> Event
Store.register_many(canaries: Iterable[Canary], *, run_id: str | None = None) -> list[Event]
Store.record(event: Event) -> Event
Store.canaries() -> list[Canary]
Store.get_canary(canary_id: str) -> Canary | None
Store.events(*, canary_id: str | None = None, action: Action | None = None,
             run_id: str | None = None, after_seq: int = 0,
             limit: int | None = None) -> list[Event]

generate(kind: str, path: str, *, template: str | None = None) -> GeneratedCanary
create_canary(store: Store, root: str | Path, path: str, *, kind: str = "env",
              template: str | None = None, run_id: str | None = None) -> Canary
seed(store: Store, root: str | Path, *, profile: str = "minimal",
     specs: Sequence[SeedSpec] | None = None, run_id: str | None = None) -> list[Canary]
```

- `Canary` is frozen, keyword-only: `kind`, `token`, `path`, `sha256`, default UUID `id`, default UTC `created_at`. `token` is hidden from repr and from `to_dict()` unless `include_token=True`. Registry entries keep no artifact content.
- `GeneratedCanary` holds `canary` and `content`; `generate` only renders in memory. `SeedSpec(path, kind, template=None)` selects a relative destination. Custom kind is `custom`; substitutions are `$token`, `$canary_id`, `$label`; `$$` is a literal dollar sign. Marker presence and synthetic labeling are mandatory, with 256 KiB template/output limits.
- `Event` is frozen, keyword-only: required `action: Action`, `source: str`; optional `canary_id`, `provenance="direct"`, `run_id`, `pid`, `destination`, `metadata`, default UUID `id`, default UTC `timestamp`, `seq=None`. Every canary event requires a registered canary UUID. `MONITOR_HEALTH` permits `canary_id=None`.
- `Action` is a string enum: `CREATE`, `READ`, `COPY`, `TOOL_USE`, `MODEL_REQUEST`, `EXFILTRATION`, `MONITOR_HEALTH`. Pass the enum to constructors. `record()` rejects CREATE and preassigned sequences; creation goes through registration. It returns a new frozen Event with its database sequence.
- `EventSink` is a runtime-checkable protocol with `record(Event) -> Event`; `Monitor` declares `start() -> None` and `stop() -> None`. Store satisfies EventSink and needs no close call because each operation closes its connection. It can be shared across threads; each process may independently instantiate it.
- Metadata is an immutable mapping of reviewed names to scalar JSON values. `METADATA_KEYS` in `models.py` includes backend/reason/error_code, tool/model, method/content_type/encoding, counts/bytes, watch_count/missing_count, attribution/confidence, path/target_path, host/port/route, and blocked/healthy. Limits: 32 fields, 512 characters per string, 4096 JSON bytes. Extend the allowlist intentionally for new adapter evidence. Never put request bodies, authorization, environment, argv or arbitrary exception text into these fields. Adapters own sanitizing destination URLs and operator-provided labels; this is not a general secret scrubber.
- `events()` orders by SQLite ingestion sequence, not wall-clock timestamp; `after_seq` supports incremental consumption. Unknown canary IDs return `None` from lookup and no rows from filters. Invalid persistence operations raise `StoreError` with a bounded SQLite error type, not a SQL statement/token dump.
- `render_report(events, *, format="text", canaries=()) -> str` is in `agentcanary.report`. Supply registry records to enrich `canary_type`; health events have null type. CLI does this automatically. JSON shape is `{"events": [...], "count": N}`. JSONL is one event per line; empty JSONL is empty output. Unknown PID displays as `unknown` in text and `null` in JSON.

CLI examples:

```text
agentcanary --state-dir ./state create aws-key
agentcanary --state-dir ./state create kubeconfig --root ./workspace --output .kube/config
agentcanary --state-dir ./state create custom --template ./template.txt --output custom.txt
agentcanary --state-dir ./state seed ./workspace --profile realistic --run-id demo --json
agentcanary --state-dir ./state report --format jsonl --action CREATE --run-id demo
agentcanary types --json
```

`--state-dir` precedes the subcommand. Default `create KIND` output is `canaries/KIND-RANDOM.txt` relative to `--root` (default current directory). Expected user errors return status 2 without a traceback.

## Decisions Made

- Runtime remains stdlib-only; development tools live in `.venv` with committed `uv.lock`.
- SQLite uses foreign keys, parameter binding, WAL, FULL synchronization, busy timeout and schema/application IDs. New state is 0700 and its database is 0600; links, hardlinks and nonprivate preexisting database files are rejected.
- Filesystem and SQLite durability are separate boundaries. Ordinary failures roll back newly created files and newly created empty directories; abrupt termination between file fsync and database commit can leave an unregistered artifact. No cross-filesystem atomicity is claimed.
- Directory descriptors prevent selected path components from following symlinks. A hostile process with the same account can still tamper with local evidence; this library is not a sandbox.
- The parent clarified that create's positional argument must be the type and event reports must expose canary type; both are implemented and tested within the planned CLI/report task.

## Deviations from Plan

No implementation-scope deviations. The CLI argument choice and report enrichment were clarified during the planned implementation. Filesystem safety tests and clean installation checks strengthen the specified acceptance criteria without expanding phase scope.

The GSD state handlers ran, but the initial minimal STATE scaffold lacked a Progress line, and the roadmap handler retained In Progress despite verified completion. Phase 1 counters/status were normalized after the SDK calls, preserving the five-phase roadmap and user model preference. No later phase was marked complete.

## Verification

- `uv run pytest -q`: **42 passed**.
- `uv run ruff check .`: **passed**.
- `uv run ruff format --check .`: **passed**.
- `uv run mypy src`: **passed**, 10 source files.
- `uv build`: **passed**, wheel and source distribution in ignored `dist/`.
- Installed wheel with `uv pip install --python .venv-wheel-check/bin/python --no-deps ...`; ran from an isolated temporary directory inside the VM. `create aws-key` and realistic seeding produced 9 artifacts/CREATE events, with types and no token values in JSONL. No network requests were made by application tests.

## Known Stubs and Deferred Issues

None. Protocol method bodies are deliberate abstract contracts. Filesystem monitoring, cooperative SDK observations, HTTP inspection and final documentation remain the separate planned phases; they are not claimed here.

## Next Phase Readiness

CORE-01 through CORE-04 are verified. Phases 2 and 3 can build adapters using EventSink and Store. Emit `pid=None` for observations without process evidence, carry explicit source/provenance, and keep metadata/body privacy boundaries. No external service setup is needed.

## Self-Check: PASSED

All listed implementation artifacts and both phase documents exist. Git confirms task commits `ff9f33e`, `eab8141`, and `7ea2b61`; ledger range contains exactly three commits with the required identity. No tracked files were deleted.
