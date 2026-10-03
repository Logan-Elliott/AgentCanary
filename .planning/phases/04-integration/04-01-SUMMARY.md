---
phase: 04-integration
plan: 01
subsystem: integration
tags: [demo, subprocess, loopback, inotify, attribution, cleanup]
requires:
  - phase: 03-network
    provides: Blocking HTTP inspection, SDK observations, registry and passive monitoring
provides:
  - Installed CLI and reusable synthetic lifecycle demonstration with retained safe evidence
  - Real process/tool/socket integration and bounded failure cleanup regressions
affects: [05-release]
tech-stack:
  added: []
  patterns: [owned-process-group, child-only-subreaper, readiness-predicates, failure-evidence]
key-files:
  created: [src/agentcanary/demo.py, tests/test_demo.py, tests/test_integration.py]
  modified: [src/agentcanary/cli.py, README.md]
key-decisions:
  - "Demo creates an exclusive private output directory with its own state and default observation policy."
  - "Only the disposable simulated child becomes a Linux subreaper; process cleanup never changes the SDK caller's child ownership."
  - "Completion requires ordered SDK evidence, passive access, blocked HTTP requests, actual tool/copy receipts and healthy shutdown."
requirements-completed: [E2E-01, E2E-02]
coverage:
  - id: D1
    description: Installed demo proves all six lifecycle actions with honest source attribution and inspectable reports
    requirement: E2E-01
    verification:
      - kind: e2e
        ref: tests/test_demo.py::test_installed_cli_demo_complete_safe_reports_and_attribution
        status: pass
    human_judgment: false
  - id: D2
    description: Concurrent sensors preserve run boundaries and failure paths cannot produce successful completion
    requirement: E2E-02
    verification:
      - kind: integration
        ref: tests/test_demo.py and tests/test_integration.py
        status: pass
    human_judgment: false
actuals:
  tokens: 8989
  tasks: 2
  commits: 3
commits: 3
plan_head_before: f34edfc30512af40c513f74d43b32d10434fd74c
plan_head_after: 93edfc40c5619e365f7f52e4311587d216525747
duration: 18min
completed: 2026-10-03
status: complete
---

# Phase 4 Plan 1: End-to-end demo and adversarial integration Summary

**A real installed Python child reads and copies a synthetic canary, invokes a consuming tool, observes mock model input and receives two HTTP 403 responses, with correlated durable evidence and verified descendant cleanup.**

## Accomplishments

- Added `agentcanary demo --directory PATH [--timeout SECONDS] [--json]` and `agentcanary.demo.run_demo(directory=None, *, timeout=15.0)`. Omitting the directory selects a unique name in the current directory. Parent directories must exist; existing paths and symlink components are refused. The output directory is private mode 0700.
- Seeded an env canary before monitor/listener readiness, then launched the installed module from the output directory with `sys.executable -m agentcanary.demo`. The child copies the fixture, invokes an actual Python tool that reads stdin and records a digest receipt, observes model input and makes two actual HTTP requests over literal `127.0.0.1` connections. The mock model and collector `.invalid` origins remain HTTP target labels.
- Required CREATE, READ, COPY, TOOL_USE, MODEL_REQUEST and EXFILTRATION for the issued ID and run. Ordered SDK events identify the child caller. Passive and HTTP actor PIDs remain unknown. Copy/tool digest receipts and child-confirmed 403 responses supplement observation events without claiming semantic use or real provider delivery.
- Retained `workspace/`, `state/`, `events.jsonl`, `report.txt`, `summary.json`, `child.json` and `tool.json`. CLI summaries and report exports contain no token values or artifact contents. Installed `report --format jsonl` reproduces exported evidence exactly.
- Used an owned process session/group and a child-local Linux subreaper to terminate and reap tool descendants after failure, timeout or interruption. Real SIGTERM/SIGINT tests and injected failures include a tool and grandchild that ignore SIGTERM; every recorded PID disappears from `/proc`, including zombie state. The SDK caller's subreaper state is untouched.
- Tested two canaries through concurrent SDK, inotify and HTTP observations with independent run labels. Verified startup refusal, missing passive evidence, HTTP sink failure, report failure and repeated isolated runs. Missing/failed evidence produces nonzero outcomes with retained failure records.

## Task Commits

1. **Installed CLI demonstration** — `2cc3db5` (`feat`).
2. **Cross-boundary integration and failure verification** — `93edfc4` (`test`).

The measured Git span contains three commits, including root-agent documentation commit `10b85b4`. Actual tokens are `ceil(35953 / 4)` over the realized diff in the five owned source/test/README files. All new commits use Logan-Elliott <dev.loganelliott@gmail.com>.

## Public Demo Contract

```python
from agentcanary.demo import DemoError, DemoResult, run_demo

result = run_demo("new-demo-directory", timeout=15.0)
result.to_dict()
```

`DemoResult` exposes `directory`, `state_dir`, `run_id`, `canary_id`, `child_pid`, `tool_pid`, `actions`, `http_statuses` and `status`. Successful actions list the six lifecycle actions; statuses are `[403, 403]` in JSON and status is `complete`. `summary.json` matches the JSON CLI output. Failures retain best-effort evidence with status `failed`; an unwritable output cannot guarantee a report. CLI failures return 2; Ctrl-C/SIGTERM return 130. Timeout bounds child execution plus passive-evidence collection after worker startup; process reaping and worker APIs impose their own bounded shutdown deadlines.

The demo uses its own `state/` beneath the output directory, regardless of global `--state-dir`. It rejects `--config`; its purpose is a fixed isolated acceptance demonstration. The text output includes a shell-quoted inspection command. Copy and tool receipts validate byte handling but do not upgrade SDK or passive attribution claims.

## Verification

- Task 1: `uv run pytest -q tests/test_demo.py` — **7 passed in 2.38s**.
- Expanded focused suite: `uv run pytest -q tests/test_demo.py tests/test_integration.py` — **19 passed in 11.60s**.
- Final full regression: `uv run pytest -q` — **184 passed in 45.46s**, no skips.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed, 80 files at verification time.
- `uv run mypy src` — passed, 17 source files, strict mode.
- `uv run agentcanary demo --help` — passed; documented options match parser output.
- Parent orchestration separately verifies clean wheel/sdist installations in Phase 5; Phase 4 tests use the installed development package from a non-repository working directory.

## Decisions and Implementation Notes

The dedicated child owns Linux subreaper behavior because the requirement includes reaping orphan tool grandchildren. Setting that flag in the reusable parent API would affect unrelated caller processes. Group signaling handles owned live processes; child cleanup kills and waits for adopted descendants. The Linux behavior is grounded in [PR_SET_CHILD_SUBREAPER documentation](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html), and subprocess lifetime handling in [Python's subprocess documentation](https://docs.python.org/3/library/subprocess.html).

Success is recorded only after worker shutdown and evidence export. Failure export writes its summary independently so an earlier partial report export cannot prevent the failed status from being recorded. Polling uses readiness or durable-evidence predicates and monotonic deadlines. No total causal order is required between kernel notifications and SDK/network observations.

## Deviations from Plan

None. Child-only descendant ownership and independent failed-summary export are implementation details of the planned failure and cleanup guarantees. No runtime dependency, external service, credential, authentication gate or user setup was added.

GSD state, metrics, decisions, session, roadmap and requirement handlers ran. As in earlier phases, generated state retained the previous phase pointer and 60% progress while recording four completed plans, and roadmap remained In Progress. State and roadmap were normalized to the verified Phase 4 completion and 80% progress; Phase 5 remains next.

## Threat Flags

| Flag | File | Description |
| --- | --- | --- |
| threat_flag: subprocess_lifecycle | src/agentcanary/demo.py | Fixed installed child and local consuming tool run in an owned session; argument arrays, discarded output, bounded waits and child-local descendant reaping. |
| threat_flag: file_access | src/agentcanary/demo.py | New exclusive private output directory and retained evidence; no-follow parent traversal and exclusive report creation; trusted controlled child receipts. |

## Boundaries and Residual Limits

The demo remains an observation test, not a hostile-process sandbox. Cleanup guarantees cover its controlled local child/tools and tested interruption paths; forced termination of the runner itself (SIGKILL), uninterruptible kernel tasks, or malicious same-account interference cannot be recovered by Python cleanup. General `Observer.run_tool()` semantics remain unchanged; the demo's child owns the additional descendant lifecycle. Passive access does not identify the actor, SDK observations identify the calling process and listener events do not authenticate the client. No real model/provider or external destination is contacted.

## Known Stubs

None. No skipped tests, unrun verification steps or unresolved defects remain in this plan.

## Next Phase Readiness

Phase 4 fulfills E2E-01 and E2E-02. Phase 5 can use the stable demo JSON and retained state as its clean-install acceptance check, complete release documentation/review and archive the milestone locally. Remote publication remains outside authorization.

## Self-Check: PASSED

All three new source/test files, SUMMARY and VERIFICATION exist. Both task commits resolve. Every required automated check passed independently, and no unexpected tracked-file deletion occurred.
