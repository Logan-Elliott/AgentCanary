# Local release acceptance

Verified 2026-10-04 UTC (2026-10-03 America/New_York). Linux x86_64 with `/proc`; AgentCanary 0.1.0; zero runtime dependencies. Application traffic stayed on loopback and all artifacts were synthetic. Final implementation: `f1bae7a`.

## Regression and compatibility

| Interpreter | Full suite | Duration |
| --- | --- | --- |
| CPython 3.11.17 | 220 passed, no skips | 64.67s |
| CPython 3.12.3 | 220 passed, no skips | 65.19s |
| CPython 3.14.8 | 220 passed, no skips | 68.43s |

Strict mypy passed for 17 source files. Ruff lint and format checks passed (87 files). The committed `uv.lock` pins development dependencies. Separate `.venv-py311` and `.venv-py314` environments preserve the default interpreter. CI also specifies Python 3.13; that interpreter and hosted CI were not run locally.

## Distribution acceptance

`uv build` produced the final wheel and source archive after all source corrections. `scripts/verify_install.py` passed for both distributions on each interpreter above: six clean installations, each with the full CLI and demo checks. Each run creates a fresh environment, removes Python path overrides, works outside the repository and verifies imports resolve inside that environment.

The verifier checks MIT metadata, zero runtime dependencies, `py.typed`, module/demo entry points, source docs/examples/tests and exclusion of local planning/config/state artifacts. It exercises help/version, AWS/kubeconfig creation, eight-artifact realistic seeding, eight passive watches, loopback proxy readiness, reports, the complete demo and JSONL/report agreement. Wheel installation uses `--no-index --no-deps`; source installation uses an isolated build backend. Backend downloads are development setup, not an application service requirement.

## Retained demonstration

`uv run agentcanary demo --directory ./agentcanary-demo-final --json` completed on the final source. The ignored private directory retains state and redacted reports. Canary `a735f6f5-50b9-4ee1-a4f6-35146b739804`, run `b7bae5a0-2806-4be2-a23a-b3463fb81f0f`: CREATE, READ, COPY, TOOL_USE, MODEL_REQUEST and EXFILTRATION, with both HTTP responses 403. Twelve records include health and independent source observations. SDK evidence identifies the child caller; passive and HTTP PID remain unknown.

The demo suite verifies distinct runs, concurrent sources, missing coverage, startup/sink/report failures, real interruption, timeouts, and termination/reaping of controlled tool descendants. Structured mock model JSON contains the actual observed input; separate tool receipts verify fixture bytes. No external provider, collector or credentials are used.

## Review and corrections

Phase 1–3 independent reviews are clean. Final review found and resolved:

1. Summary publication after failed synchronization — temporary private files are synchronized before exclusive publication (`20c7d36`).
2. Group signaling after process identity ownership ended — completion uses `waitid` without reaping until final group cleanup (`20c7d36`).
3. A real concurrent SQLite sidecar deletion race — narrowly bounded revalidation of safe zero-link optional sidecars (`f1bae7a`).

The race was found by the first release rerun (193 passed, one failed), then confirmed by real concurrent reads before correction. All final suites above include its 26 deterministic/stress regressions. Independent reviewer checks passed all ten demo correction tests and all 26 sidecar tests; `05-REVIEW.md` has zero outstanding findings and retains original severities/evidence.

All relative links resolve in eight public Markdown documents. SDK, policy and custom-template examples ran successfully in disposable fixtures. Public source/docs contain no placeholder features or unfinished demo prose. CLI help is covered by installed-package acceptance.

## Material boundaries

Linux/proc is the supported platform. Passive reads and HTTP requests cannot identify actor PID. Coverage depends on configured snapshots/integrations, with health diagnostics for gaps. The HTTP endpoint always blocks and cannot inspect bypassing sockets or encrypted tunnels. SDK observations describe supplied input, not semantic consumption or provider delivery. Local evidence is not protected against a hostile process controlling the same account. These boundaries are documented and tested; they are not deferred implementation claims.
