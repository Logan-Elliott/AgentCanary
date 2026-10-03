# Local release acceptance

Date: 2026-10-03. Platform: Linux x86_64 with `/proc`. Package: AgentCanary 0.1.0, zero runtime dependencies. All application traffic was loopback-only and every artifact synthetic.

## Regression and compatibility

| Interpreter | Full suite | Duration |
| --- | --- | --- |
| CPython 3.11.17 | 184 passed, no skips | 51.39s |
| CPython 3.12.3 | 184 passed, no skips | 45.46s |
| CPython 3.14.8 | 184 passed, no skips | 54.86s |

Strict mypy passed for 17 source files. Ruff lint and format checks passed. The development environment uses the committed `uv.lock`; separate `.venv-py311` and `.venv-py314` environments avoid replacing the default interpreter. A CI definition also covers Python 3.13; no hosted CI execution is claimed.

## Distribution acceptance

`uv build` produced a wheel and source archive. `scripts/verify_install.py` passed on all three interpreters above. Each invocation creates separate fresh environments for wheel and source installation, removes Python path overrides, works outside the repository and verifies the installed import resolves inside that environment.

The verifier checks MIT metadata, no runtime dependency, `py.typed`, module/demo entry points, source docs/examples/tests, and exclusion of local planning/config/state artifacts. It then exercises CLI help/version, AWS/kubeconfig creation, the eight-artifact realistic profile, eight passive watches, loopback proxy readiness, reporting, the complete demo and JSONL/report agreement. Wheel installation uses `--no-index --no-deps`; source installation builds through an isolated backend with no runtime dependencies.

## Retained demonstration

`uv run agentcanary demo --directory ./agentcanary-demo-release --json` completed locally. The ignored private output directory contains inspectable state and redacted reports. Its six-action chain is CREATE, READ, COPY, TOOL_USE, MODEL_REQUEST and EXFILTRATION. Both HTTP responses were 403. SDK evidence identifies the actual child; passive and HTTP evidence leave PID unknown.

The automated demo suite additionally verifies distinct runs/canaries, concurrent sources, missing coverage, startup/sink/report failures, real interruption and timeouts, and termination/reaping of controlled tool descendants, including a SIGTERM-ignoring grandchild. No fixed external service or credentials are needed.

## Documentation and review

All relative links resolve in the eight public Markdown documents. SDK, policy and custom-template examples executed successfully in disposable fixtures. No TODO, FIXME, placeholder feature or unfinished demo prose remains in public source/docs. CLI help is included in installed-package checks.

Phase 1–3 independent reviews are clean after corrections. Phase 5 review found summary-publication and process-group ownership defects in the demo. Demo corrections in `20c7d36` passed independent review and ten focused regressions. The subsequent full suite found one transient SQLite sidecar validation race (193 passed, one failed); correction and full rerun remain pending. Clean wheel/sdist installations after the demo corrections passed on all three interpreters. The measurements above are historical and do not by themselves mark the milestone complete.

## Material boundaries

Linux/proc is the supported platform. Passive reads and HTTP requests do not identify actor PID. Monitoring covers configured snapshots/integrations, with explicit health diagnostics for gaps. The HTTP endpoint always blocks and does not inspect bypassing sockets or encrypted tunnels. The SDK observes supplied input, not semantic use or provider delivery. Local evidence is not protected against a hostile process controlling the same account.
