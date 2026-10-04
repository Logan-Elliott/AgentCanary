---
phase: 01-foundation
status: passed
verified: 2026-10-03
requirements: [CORE-01, CORE-02, CORE-03, CORE-04]
score: 4/4
---

# Phase 1 Verification

Foundation requirements are satisfied by the implementation at `7ea2b61` and its installed wheel. Later monitoring/network capabilities were not evaluated or marked complete.

| Requirement | Evidence | Result |
|---|---|---|
| CORE-01 | Eight parametrized built-in checks assert unique identifiers/tokens, mandatory synthetic labels, marker inclusion, content digest, no valid SSH/provider key prefixes. | Passed |
| CORE-02 | Custom-template validation; profile creation; traversal, absolute, symlink, reserved-state, collision, existing-file and readonly rejection; preflight race and partial-write/store-failure rollback checks. | Passed |
| CORE-03 | Registry/event round trip; atomic duplicate-batch rollback; foreign key enforcement; immutable bounded metadata; private state; corruption/version/unrecognized schema validation; 30 threaded registrations and 48 multiprocess events with unique durable sequences. | Passed |
| CORE-04 | CLI subprocess tests cover help/version/types, positional type creation/default unique paths, custom templates, profile seeding, graceful errors, all report formats, canary type enrichment and filters. Strict typing and clean wheel CLI smoke also pass. | Passed |

## Automated Checks

```text
uv run pytest -q                         42 passed in 6.93s
uv run ruff check .                     All checks passed
uv run ruff format --check .             All files formatted
uv run mypy src                         No issues in 10 source files
uv build                                Wheel and source distribution built
```

Built `dist/agentcanary-0.1.0-py3-none-any.whl` and `dist/agentcanary-0.1.0.tar.gz`. Installed the wheel without dependencies into `.venv-wheel-check` and ran its console script outside the repository working directory. Creating `aws-key` plus an eight-type realistic profile yielded nine CREATE events; every JSONL event included its canary type and no token values. Temporary application data was removed afterwards.

The earlier coverage run reported 79% aggregate coverage with 37 tests; CLI subprocesses were not instrumented, so the displayed CLI coverage was 0% despite passing subprocess checks. Coverage percentage is not used as phase acceptance evidence. The final expanded suite contains 42 passing tests.

## Safety and Limits

- Tests used only temporary local artifacts and synthetic markers. No application test makes an external network request.
- Store connections use WAL, FULL synchronization, foreign keys, a busy timeout, and parameterized inputs. Failed batch registration cannot leave a partial registry/CREATE batch.
- Artifact creation uses exclusive opens and no-follow directory descriptors. Tests verify symlinks inserted after preflight are refused.
- New state directory/database modes are 0700/0600; artifact files are 0600. Preexisting content is retained on failures.
- A process crash between filesystem writes and SQLite registration can leave unregistered files. Same-user hostile tampering is outside the observation tool's protection boundary.
- Custom templates and operator labels remain trusted inputs; they are inert strings and bounded, not a general credential detector. HTTP adapters must sanitize URL credentials/query strings before recording destinations.
- No unresolved stubs, skipped tests, unrun plan checks, or phase-blocking defects were found.

## Result

Passed. The core APIs and their constraints are recorded in `01-01-SUMMARY.md` for subsequent phases.

## Final release cross-check

The earlier counts above describe this phase's original execution. After all review corrections through `f1bae7a`, the complete release suite passes **220 tests without skips** on Python 3.11.17, 3.12.3 and 3.14.8. Final wheel/source installations and the full demo pass on all three interpreters. Ruff lint/format and strict typing pass. Resolved review findings and exact evidence are recorded in `../05-release/05-REVIEW.md` and `../05-release/05-ACCEPTANCE.md`; this supersedes the original implementation snapshot for release acceptance without erasing its history.
