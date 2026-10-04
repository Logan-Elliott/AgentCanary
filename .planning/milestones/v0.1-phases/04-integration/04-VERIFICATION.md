---
phase: 04-integration
verified: 2026-10-03T23:32:01Z
status: passed
score: 3/3 must-have truths verified
requirements: [E2E-01, E2E-02]
---

# Phase 4 Verification

**Verdict: PASSED.** All planned runtime boundaries and failure behavior have automated evidence. The final regression passed 184 tests with no skips; lint, formatting, strict typing and demo help passed separately.

| Must-have truth | Concrete evidence | Result |
| --- | --- | --- |
| Installed CLI demonstrates creation, access, propagation and blocked transmission | `test_installed_cli_demo_complete_safe_reports_and_attribution` launches CLI outside the checkout, then an installed-module child and real tool. Six action types, two HTTP 403 responses, matching copied bytes/digest receipts, safe exports and report round-trip are asserted. | Pass |
| Source-specific attribution and common issued/run IDs survive process boundaries | The same test verifies child SDK PID, distinct tool PID and unknown passive/HTTP PID. `test_two_canaries_concurrent_sensors_keep_run_boundaries_and_report_roundtrip` verifies two issued markers and separate SDK, network and passive run labels concurrently. | Pass |
| Failure paths terminate predictably without false completion | Startup failure, zero watches, HTTP sink failure, absent passive evidence and disk/report failures retain failed status. Real SIGTERM/SIGINT and failure/timeout tests prove controlled agent, tool and SIGTERM-ignoring grandchild PIDs disappear from `/proc`. | Pass |

## Commands and Outcomes

Each command was run through `rtk proxy`, with its exit status checked independently.

| Command | Outcome |
| --- | --- |
| `uv run pytest -q tests/test_demo.py tests/test_integration.py` | 19 passed, 11.60s |
| `uv run pytest -q` | 184 passed, 45.46s, no skips |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed, 80 files |
| `uv run mypy src` | Passed, 17 source files, strict |
| `uv run agentcanary demo --help` | Passed |

## Requirement Closure

- **E2E-01:** Complete real child/tool/passive-monitor/mock-model/HTTP chain with durable retained reports and exact CLI instructions in README.
- **E2E-02:** New realistic process/sensor/failure tests supplement Phase 1–3 matching, false-positive/negative, unsupported protocol, encoding, concurrent writer and attribution coverage. The full suite verifies these together.

No stubs, skipped tests, unrun checks or external setup remain. Real application connections are literal loopback; `.invalid` request labels do not become connection targets. Evidence makes no provider-delivery or passive actor-attribution claim. Clean wheel/sdist verification and final release review belong to Phase 5.

## Final release cross-check

The earlier counts above describe this phase's original execution. After all review corrections through `f1bae7a`, the complete release suite passes **220 tests without skips** on Python 3.11.17, 3.12.3 and 3.14.8. Final wheel/source installations and the full demo pass on all three interpreters. Ruff lint/format and strict typing pass. Resolved review findings and exact evidence are recorded in `../05-release/05-REVIEW.md` and `../05-release/05-ACCEPTANCE.md`; this supersedes the original implementation snapshot for release acceptance without erasing its history.
