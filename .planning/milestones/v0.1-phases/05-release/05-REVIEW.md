---
phase: 05-release
reviewed: 2026-10-03T23:35:59Z
depth: deep
files_reviewed: 23
files_reviewed_list:
  - src/agentcanary/demo.py
  - src/agentcanary/cli.py
  - src/agentcanary/filesystem.py
  - src/agentcanary/store.py
  - tests/test_demo.py
  - tests/test_demo_release.py
  - tests/test_store_sidecars.py
  - tests/test_integration.py
  - scripts/verify_install.py
  - pyproject.toml
  - .github/workflows/ci.yml
  - README.md
  - docs/architecture.md
  - docs/threat-model.md
  - docs/limitations.md
  - docs/integrations.md
  - examples/custom-template.txt
  - examples/observe_workspace.py
  - examples/policy.toml
  - CONTRIBUTING.md
  - SECURITY.md
  - CHANGELOG.md
  - LICENSE
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
historical_findings:
  critical: 3
  warning: 0
  info: 0
  total: 3
status: clean
resolution_status: resolved
reviewed_implementation: 2a0cdc6073fb2195d8dc47831176aff840147851
fixes_verified_through: f1bae7aa73ea155c8ab7e0271084b490e818bc06
fixes_verified: 2026-10-04T00:02:38Z
reused_reviews:
  - .planning/phases/01-foundation/01-REVIEW.md
  - .planning/phases/02-observations/02-REVIEW.md
  - .planning/phases/03-network/03-REVIEW.md
---

# Phase 5: Whole-project Code Review Report

**Reviewed:** 2026-10-03T23:35:59Z  
**Depth:** deep  
**Files reviewed in this pass:** 23, including the focused correction tests and Store call sites, with resolved Phase 1–3 source reviews reused  
**Status:** resolved — no outstanding findings; canonical workflow status `clean`  
**Corrections verified:** 2026-10-04T00:02:38Z

## Summary

The final integration review found two historical BLOCKER defects in the demo's failure and cleanup behavior. A failed final summary write could retain a valid completion claim, and process-group cleanup used a numeric group identity after the leader had been reaped. Both are resolved by `20c7d36`: the correction source was independently inspected and all ten dedicated release regressions passed. Subsequent release-suite execution exposed a third BLOCKER regression: normal SQLite sidecar deletion could cause a false unsafe-file rejection during concurrent Store operations. Its correction in `f1bae7a` was independently inspected and all 26 dedicated sidecar regressions passed. Original severity and evidence remain below; `findings` counts outstanding issues and `historical_findings` preserves the original totals. No material findings remain in the reviewed scope.

The original baseline is committed tree `2a0cdc6`, including demo implementation/tests through `93edfc4`. Correction verification reads the focused implementation/test changes in `20c7d36`, README clarification in `74985ca`, and sidecar validation changes/tests in `f1bae7a` with their Store callers. Review of the remaining foundation, observation and network layers reuses their completed deep reviews and independently verified corrections. This pass reads the new demo, CLI wiring, integration tests, installation verifier, package configuration, CI definition and release documentation, then traces their connections to those existing contracts. Concurrent GSD state updates and untracked local execution tooling were excluded. No structural pre-pass or external-reviewer evidence was supplied.

## Narrative Findings (AI reviewer)

### CR-01: Failed summary finalization leaves evidence claiming completion

**Classification:** BLOCKER  
**Requirements:** E2E-01, E2E-02, REL-03  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/demo.py:59-70`, `203-209`, `285-295` at `2a0cdc6`  
**Disposition:** Resolved by `20c7d36`; source correction and dedicated failure/publication regressions independently verified.

**Issue:** `_write()` creates the final destination exclusively, writes and flushes its content, and only then calls `fsync()`. The successful export path supplies a summary whose status is `complete`. If finalization of that summary fails, `run_demo()` raises a failure, but the already-created summary can still contain the complete JSON document. The failure handler attempts another exclusive creation of the same pathname. Its `FileExistsError` is suppressed, leaving the original completion claim in the retained evidence. This violates the documented promise that a failed demo does not claim completion.

**Evidence:** A benign temporary fixture invoked `_export(directory, None, {"status": "complete"})` with `os.fsync` patched to raise an ordinary synthetic `OSError`. The export raised `OSError`; the failure handler's subsequent `_write(..., {"status": "failed"})` behavior raised `FileExistsError`; the retained JSON still parsed with status `complete`. No secret, network request or external process was involved. The existing export-failure regression injects failure while writing `report.txt`, before the complete summary exists, so it does not exercise this boundary.

**Fix:** Finalize summary contents in an owned temporary file and publish the completion pathname only after required writes and synchronization succeed. Clean up failed owned temporary writes, and ensure failure reporting cannot leave a stale completion claim. Preserve exclusive/no-follow behavior and refusal to overwrite unrelated files. Add a regression for final summary flush/synchronization failure, asserting the demo fails and no retained summary claims completion.

**Verified correction:** `_write()` now creates a private, exclusive temporary file relative to the opened parent directory, writes/flushes/synchronizes it, then publishes with an exclusive hard link. Cleanup removes the owned temporary name on success or failure. A failed file synchronization occurs before the public pathname exists. Dedicated real-demo regressions cover both one-time and persistent summary synchronization errors: the retained summary respectively reports failure or remains absent, with no completion publication or leftover temporary file. Separate tests verify that existing regular files and symlink destinations are preserved.

### CR-02: Demo cleanup signals a process-group identity after relinquishing ownership

**Classification:** BLOCKER  
**Requirements:** OBS-03, E2E-02, REL-03  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/demo.py:103-117`, `245-280` at `2a0cdc6`  
**Disposition:** Resolved by `20c7d36`; ownership/order regressions and real unreaped-leader integration independently verified.

**Issue:** The normal execution loop calls `child.wait()` and reaps the session leader before receipt validation, database reads and final cleanup. The registered `_stop_child()` callback then sends signals to `child.pid` as a process-group number without checking whether that identity is still owned. It also sends an unconditional final `SIGKILL` after its own `wait()`. Once the original group is empty and the leader has been reaped, that numeric identity can be reused. Cleanup can therefore address a different process group. Separate sessions establish the original group boundary but do not preserve ownership of a recycled numeric identifier.

**Evidence:** Source tracing shows the successful `wait()` at line 253 precedes the exit-stack callback and subsequent database/receipt checks. A mocked completed `Popen` with `returncode=0` confirms `_stop_child()` still issues both `SIGTERM` and `SIGKILL`. The reuse consequence follows from relinquishing the child identity before signaling; no attempt was made to force PID recycling or signal an unrelated process. Existing descendant tests verify termination and reaping of actual owned children, but do not assert that signals stop when identity ownership ends.

**Fix:** Preserve the leader as an unreaped child while inspecting completion and performing any group cleanup, for example with Linux `waitid(..., WNOWAIT)`, and reap only after all necessary group signals. Alternatively avoid all group signaling once the controlled leader has already been reaped, with the resulting descendant-cleanup boundary made explicit. Remove unconditional signals after final reaping. Add a regression that fails on any signal after ownership has ended while retaining real descendant timeout, interruption and failure tests.

**Verified correction:** The execution loop observes exit using `waitid` with `WNOWAIT`, preserving the leader's reserved identity through verification and cleanup. Group signals occur before the single final `child.wait()`. Cleanup skips signaling when `returncode` is already set or `waitid` reports the child has been reaped, and there is no post-reap signal. Dedicated tests verify signal/reap order for normal and forced cleanup, three already-reaped/external-waiter cases, and an actual completed demo child remaining waitable through chain verification before final reaping. Concurrent ownership of the same child by an arbitrary external waiter is not an added supported lifecycle contract.

### CR-03: Normal SQLite sidecar deletion can fail concurrent Store operations

**Classification:** BLOCKER  
**Requirements:** CORE-03, OBS-03, E2E-02, REL-01, REL-03  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/filesystem.py:52-63` before `f1bae7a`; `/home/gsd/projects/agent-canary/src/agentcanary/store.py:50-60`  
**Disposition:** Resolved by `f1bae7a`; discovered by the orchestrator's final release suite, with correction source, Store call sites and 26 dedicated tests independently verified.

**Issue:** Each Store connection checks the primary database and optional SQLite sidecars before opening SQLite. The previous validator rejected every stat result whose link count was not exactly one. During ordinary last-connection cleanup, SQLite may unlink an optional sidecar after pathname lookup has retained its inode but before the metadata is sampled. A zero-link result then describes a disappearing file, and immediate rejection fails an otherwise legitimate Store operation. This can interrupt evidence reads or recording under the concurrency contract.

**Evidence:** The orchestrator reported a full-suite failure in a policy test while an inotify writer and Store reader operated concurrently. The diagnostic recorded in `05-STORE-RACE.md` reproduced one real shared-memory sidecar sample with `nlink=0`, regular-file type, current UID 1000 and private mode 0600, followed by `UnsafePathError`, during 4,000 benign Store reads. That diagnostic was supplied evidence, not rerun by this reviewer. Independent source inspection confirms the previous unconditional `st_nlink != 1` rejection, the optional-sidecar callers, and the corrected behavior exercised by the dedicated deterministic tests and real concurrency check.

**Fix:** Revalidate a disappearing optional sidecar through a small bounded number of no-follow stat attempts. Limit that exception to the exact SQLite sidecar names. Accept only a missing optional path or a valid singly linked replacement; retain immediate rejection of unsafe type, ownership, permissions or multiple links and propagate unrelated filesystem errors. Primary, required and unrelated optional files must retain their original validation semantics.

**Verified correction:** The validator makes at most three no-follow stat attempts only when `missing_ok=True`, the name is exactly `events.sqlite3-wal`, `events.sqlite3-shm` or `events.sqlite3-journal`, and the observed zero-link file otherwise passes every existing attribute check. Missing optional paths and valid replacements are accepted; persistent zero-link samples fail closed. Tests cover replacement/disappearance, the retry bound and final allowed attempt, primary/required/unrelated names, unsafe initial/replacement samples and error propagation. A real four-Store stress case verifies all 400 writes, unique IDs, contiguous sequences and per-writer counts during reader activity, then exercises 1,600 read-only operations. All 26 cases passed independently. This bounded correction does not promise success under every possible repeated unlink schedule.

## Architecture and requirement assessment

| Area | Requirements | Assessment and retained boundary |
| --- | --- | --- |
| Synthetic artifacts and filesystem safety | CORE-01, CORE-02 | Reused foundation review verifies issued markers, inert built-ins, exclusive creation, no-follow traversal, rollback and canonical paths. Custom templates remain trusted operator text; arbitrary literals cannot be certified secret-free. |
| Durable state and concurrency | CORE-03, OBS-03 | SQLite transactions, per-operation connections, busy handling, private state checks and schema validation are wired through all sources. CR-03 is resolved by bounded validation retries for otherwise-safe disappearing optional SQLite sidecars. Filesystem creation and database commit remain separate crash boundaries, explicitly documented. The store is local evidence, not tamper-resistant storage against the same account. |
| CLI, package and reports | CORE-04, REL-01 | CLI entry point, type marker, license metadata, source inclusion and independent wheel/source installation checks agree. Demo arguments run before ordinary state construction, use an isolated directory and explicitly reject external policy configuration. CR-01 is resolved by publication only after content synchronization. |
| False positives and meaning | OBS-01, OBS-02, E2E-02 | Passive reads describe inode access; cooperative observations describe supplied inputs or invocation attempts. Legitimate readers and duplicate source observations are expected. The code and documentation do not equate marker sightings with malicious intent or semantic consumption. |
| False negatives and coverage | OBS-01, OBS-03, NET-02, E2E-02 | Registry snapshots, inode changes, lost watches, queue loss and bounded parser failures have explicit diagnostics. Unsupported access mechanisms, marker transformations and splits across independent fields/operations remain disclosed gaps. Prior duplicate-inode and duplicate-JSON-member findings are resolved. |
| Attribution and correlation | OBS-01, OBS-02, NET-03, E2E-01 | SDK caller PID, unknown passive/HTTP PID and operator run labels remain distinct. The demo checks source-specific evidence, a separate real tool receipt and content digests before reporting success. Correlation is not proof of causal ordering or authenticated agent identity. |
| Process and thread lifecycle | OBS-03, E2E-02 | Workers register cleanup, readiness and failure checks. A dedicated demo child owns the subreaper setting, leaving SDK callers' process-wide behavior unchanged. Existing tests exercise descendant shutdown, interruption and timeout; CR-02 is resolved by retaining the unreaped leader through group signaling. Arbitrary hostile-process containment is outside scope. |
| Network boundary and policy | NET-01, NET-02, NET-03 | Reused network review traces bounded framing/decoding, loopback-only listener, no upstream connection path, immutable safe event metadata, retained policy annotations and presentation-only filtering. Prior redacted-origin identity issue is resolved. Direct sockets, other proxies, TLS/QUIC and traffic outside the adapter remain unobserved. |
| Payload privacy | CORE-01, NET-03, E2E-01 | Adapter events and exported reports exclude raw payloads, raw argument arrays and authorization values. The demo intentionally retains synthetic source/copy artifacts inside a private directory; these are distinct from payload-free event evidence. The low-level Event API is not a universal secret scrubber. |
| Portability | CORE-04, REL-01, REL-02 | Linux, `/proc`, inotify and demo subreaper requirements are stated. The pure-Python wheel tag does not imply cross-platform behavior. Python 3.11–3.14 CI is configured; actual execution evidence is tracked separately below. |
| Tests and installation | E2E-02, REL-01 | New integration tests cover concurrent independent processes, ingestion sequence, source-specific attribution, report round trips and loopback-only connections. The installation verifier inspects archive contents and exercises installed CLI/create/seed/monitor/proxy/report/demo outside the checkout. Ten dedicated demo release regressions and 26 sidecar cases cover the three findings, structured mock model input and concurrent Store validation. |
| Documentation and usability | REL-02 | README, architecture, threat model, limitations, integration examples, contribution/security guidance, changelog and license describe the actual supported boundaries. Help and documented examples match current interfaces. No unfinished product content was found in this scope. README's build-tool locking description was clarified in `74985ca`. |
| Local release completion | REL-03 | Review findings are resolved. Final release-wide checks and the local GSD archive/state work remain the orchestrator's acceptance responsibilities. No remote publication is part of this review. |

The principal architectural tradeoff is explicit observation inside an operator-controlled environment. This architecture can produce useful evidence without pretending to provide whole-machine egress control, cryptographic causality or resistance to another process with the same credentials. Documentation consistently states that boundary; it is not an additional defect.

## Verification evidence and limits

Independent verification in this pass consists of source/test/document review and two narrowly scoped benign checks: the final-summary synchronization failure and mocked signaling of an already-reaped child described above. Their outputs confirmed the retained `complete` status and signals `[SIGTERM, SIGKILL]`, respectively. The temporary fixture was automatically removed. No whole-suite, build or installation run was duplicated while the orchestrator was running release verification.

For final correction verification, the reviewer inspected the `20c7d36` diff and independently ran `rtk proxy .venv/bin/python -m pytest -q tests/test_demo_release.py`: **10 passed in 3.67 seconds**. The source/test working tree matched the committed correction. Beyond the two finding regressions, this verifies that the completed child remains unreaped until cleanup and the mock model request contains the structured JSON input actually sent to the local endpoint, while the collector receives the synthetic artifact bytes. The orchestrator reported **29 focused demo/integration/release tests passed**, plus scoped lint/format and strict source typing; those broader results are reported evidence rather than a duplicate reviewer run. No additional defect was identified in the narrow correction scope.

The subsequent sidecar correction was independently checked against `f1bae7a`, its Store connection call sites and `05-STORE-RACE.md`. Running `rtk proxy .venv/bin/python -m pytest -q tests/test_store_sidecars.py` produced **26 passed in 14.77 seconds**. The source/test working tree matched the committed correction. The orchestrator/executor separately reported **66 focused tests passed in 14.55 seconds**, the full Python 3.12 suite **220 passed in 65.19 seconds**, full lint/format checks for 87 files and strict mypy for 17 source files. Those broader outcomes are attributed reports rather than independent reviewer runs. No remaining issue was identified in the sidecar correction.

Earlier independent correction verification remains recorded in the reused phase reviews: foundation corrections; four focused monitor lifecycle/duplicate-inode tests; the exact argv snapshot regression; and six network inspection-boundary tests. Those checks establish the specific corrected behavior and do not imply exhaustive scheduling or parser coverage.

After the final sidecar source correction, the orchestrator rebuilt the distributions and reported all six fresh wheel/source installations and installed CLI/monitor/proxy/demo checks passing outside the checkout on Python 3.11, 3.12 and 3.14. Python 3.11/3.14 full-suite reruns were in progress during this final correction verification; their final counts and outcomes are not asserted here without the subsequent release record. The installation verifier and CI configuration were read, but this reviewer did not independently rerun them. Remote GitHub Actions execution, action-commit availability, external package resolution and untested platforms remain unverified by this review.

One minor documentation precision issue was corrected in `74985ca` and independently inspected: README line 26 now distinguishes development dependencies pinned by the lockfile from the isolated Hatchling backend's declared version range. This avoids implying a fully pinned isolated build and is not counted as a separate material code finding.

Only local benign synthetic checks were used. No exploit reproduction, third-party probe, host/shared-mount access, external transmission, push, PR or deployment was performed. This reviewer changed only this review artifact and did not edit implementation/tests or commit.

---

_Reviewer: foundation_review_astra (gsd-code-reviewer)_  
_Depth: deep_
