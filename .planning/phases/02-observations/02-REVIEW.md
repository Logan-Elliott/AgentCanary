---
phase: 02-observations
reviewed: 2026-10-03T22:38:21Z
depth: deep
files_reviewed: 11
files_reviewed_list:
  - src/agentcanary/matching.py
  - src/agentcanary/sdk.py
  - src/agentcanary/monitors/inotify.py
  - src/agentcanary/monitors/__init__.py
  - src/agentcanary/cli.py
  - src/agentcanary/__init__.py
  - tests/test_observer.py
  - tests/test_monitor.py
  - tests/test_observation_failures.py
  - tests/test_monitor_lifecycle.py
  - tests/test_policy.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
historical_findings:
  critical: 1
  warning: 3
  info: 0
  total: 4
status: clean
resolution_status: resolved
reviewed_implementation: 25f3e2044034998c4be08c1bacbae01952503c96
fixes_verified_through: 40ab6de3bd50524e0e9760112c1c979767063555
fixes_verified: 2026-10-03T23:00:31Z
---

# Phase 2: Code Review Report

**Reviewed:** 2026-10-03T22:38:21Z  
**Depth:** deep  
**Files reviewed:** 11, including two files containing focused correction tests  
**Status:** resolved — no outstanding findings; canonical workflow status `clean`  
**Final correction verified:** 2026-10-03T23:00:31Z

## Summary

The committed Phase 2 implementation contained one BLOCKER and three WARNING findings. An accepted registry shape silently replaced passive coverage for a canary; failed monitor startup left an unstarted thread in lifecycle state; startup interruption was converted into an ordinary monitor failure; and mutable tool arguments could differ between evidence collection and invocation. Commit `308b096` resolves the three monitor findings, and `40ab6de` resolves the SDK argument snapshot finding. All four are now resolved; historical severities and evidence remain below.

All original source analysis used commit `25f3e20`, which includes the completed `af627bd` monitor implementation and subsequent failure tests. Unfinished Phase 3 changes to SDK, matching, CLI and network code were excluded. Correction verification was limited to the relevant changes in `308b096` and the argument snapshot change and regression in `40ab6de`. Frontmatter `findings` counts outstanding issues, while `historical_findings` and the narrative retain original classifications.

## Narrative Findings (AI reviewer)

### CR-01: A second registered canary silently replaces an existing inode watch

**Classification:** BLOCKER  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/monitors/inotify.py:251-255` at `25f3e20`; read emission at `325-336`  
**Disposition:** Resolved by `308b096` through explicit rejection of duplicate-inode coverage, preserving the original watch.

**Issue:** The registry accepts different canary records for the same file, including a file containing both issued markers with both records carrying the matching content digest. Both snapshots pass validation. Inotify returns the existing watch descriptor for the same inode, and assigning `_watches[wd] = snapshot` silently replaces the first record. A subsequent access therefore emits evidence only for the second record. Aggregate missing coverage is indicated by the count, but the displaced canary receives no explicit rejection or lost-coverage diagnostic.

**Evidence:** A normal local fixture combined two generated synthetic marker contents in one regular file and registered two valid records with the matching digest. Startup installed one kernel watch. A real file read produced evidence for only the second registered canary; the first was absent. This required no concurrency or hostile modification.

**Fix:** Either represent all supported canaries sharing a kernel watch, or make one-canary-per-inode an explicit monitor boundary: preserve existing coverage and emit a diagnostic identifying every additional rejected canary. Keep per-canary coverage accounting clear when reporting missing coverage.

**Verified correction:** The parent selected the explicit boundary. Duplicate watch descriptors now preserve the first snapshot and emit `MONITOR_HEALTH` with `reason="duplicate_inode"` and the skipped canary ID. The focused regression confirms the diagnostic and a real subsequent read attributed to the retained canary. The passive monitor's one-canary-per-inode limit should remain visible in release documentation; the cooperative matcher continues to support multiple issued markers in a payload.

### WR-01: Cleanup after a failed thread start joins a thread that never started

**Classification:** WARNING  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/monitors/inotify.py:260-281` and `376-388` at `25f3e20`  
**Disposition:** Resolved by `308b096`; lifecycle and restart regression passed independently.

**Issue:** If `Thread.start()` raises, `start()` closes the backend but retains the unstarted thread in `_thread`. A caller performing ordinary cleanup with `stop()` then receives `RuntimeError: cannot join thread before it is started`, replacing the useful monitor error with a second cleanup failure. Existing partial-start tests checked watches and descriptors but did not call `stop()` after the failure.

**Evidence:** With a benign injected thread-start failure, `start()` raised `MonitorError`, followed by the raw join `RuntimeError` from `stop()`. No worker remained alive and no watches remained, so descriptor leakage is not claimed for this case.

**Fix:** Discard an unstarted or fully terminated thread during failed-start cleanup. Preserve the recorded monitor error for `check()`/`stop()` and clear readiness. Test repeated cleanup and successful restart after removing the injected failure.

**Verified correction:** Failed-start cleanup now clears `_thread` and `ready` after resources are closed. The regression asserts that `stop()` exposes the retained `MonitorError`, descriptors remain unchanged, and the same monitor can subsequently start successfully.

### WR-02: Startup cancellation loses its interrupt semantics

**Classification:** WARNING  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/monitors/inotify.py:268-281` at `25f3e20`; CLI handlers `/home/gsd/projects/agent-canary/src/agentcanary/cli.py:150-157`  
**Disposition:** Resolved by `308b096`; both interruption regressions passed independently.

**Issue:** The broad startup cleanup handler catches `KeyboardInterrupt` and `SystemExit` and replaces them with `MonitorError`. Thus Ctrl-C during snapshot setup follows the CLI's status-2 failure handler instead of its status-130 interruption handler. Library callers likewise lose the cancellation exception they expect to propagate. The post-readiness signal tests do not cover this startup path.

**Evidence:** A synthetic `KeyboardInterrupt` raised while taking the initial snapshot emerged from `start()` as `MonitorError("monitor startup failed")`. Resources were closed, but the original cancellation type was lost.

**Fix:** Perform cleanup for all exceptional exits, then re-raise `KeyboardInterrupt` and `SystemExit` unchanged. A bounded `startup_interrupted` health diagnostic is appropriate when the sink remains available.

**Verified correction:** The correction re-raises both cancellation types after cleanup and attempts the dedicated diagnostic. Tests assert preserved exception type, unchanged descriptor count, cleared readiness, safe subsequent `stop()`, and the diagnostic reason.

### WR-03: Tool evidence and execution use different snapshots of mutable arguments

**Classification:** WARNING  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/sdk.py:226-252` at `25f3e20`  
**Disposition:** Resolved by `40ab6de`; the implementation and targeted regression were independently verified.

**Issue:** `run_tool()` validates and scans the caller's `Sequence[str]`, persists invocation-attempt events through the sink, and only then creates `list(argv)` for subprocess execution. An ordinary list shared with another thread or a sink callback can change between these steps. The persisted marker evidence can then describe arguments different from those actually supplied to the subprocess. The implementation already freezes bytes/text input; argv needs the same stable per-call treatment.

**Evidence:** A local sink callback changed a caller-owned argument list after persisting its TOOL_USE event. A stub captured the arguments passed to `subprocess.run`; they no longer contained the issued marker even though one corresponding invocation-input event had been recorded. No real subprocess was launched in this check.

**Fix:** Copy argv to an immutable sequence once at method entry, while preserving rejection of a bare string/bytes value. Use that single snapshot for element validation, size checks, token matching and subprocess arguments. Add a benign callback-mutation regression asserting that evidence and captured execution arguments refer to the same snapshot.

**Verified correction:** `run_tool()` now creates `arguments = tuple(argv)` after rejecting bare string/bytes input and uses that snapshot for validation, bounds, matching and execution. The reviewer independently ran `tests/test_policy.py::test_argument_snapshot_matches_actual_invocation_after_sink_mutation` against committed modules from `40ab6de`: **1 passed**. The regression confirms a sink callback can mutate the caller's list while the original observed argument snapshot is still passed to the stubbed execution function.

## Verification and scope limits

The deep review traced registry loading and matching into each Observer method, copy completion into event persistence, tool input into bounded matching and subprocess invocation, monitor snapshot validation into watch installation and event batching, and worker/sink exceptions into check/stop and CLI teardown. All scoped source and observation tests were read. Supporting immutable model, filesystem and Store contracts were cross-referenced with the completed foundation review.

The four finding checks ran against committed Phase 2 modules loaded from Git objects in memory, preventing unfinished Phase 3 edits from affecting the results. They used disposable local synthetic fixtures, normal file access and bounded fault injection. All fixtures were removed. No source files or tests were changed by this reviewer, and no commit was made.

Correction verification independently ran `tests/test_monitor_lifecycle.py` against committed modules from `308b096`: **4 passed**, followed by the single argv regression against `40ab6de`: **1 passed**. The parent reported **16 monitor/lifecycle tests passed** plus scoped lint, format and type checks. The full suite was not repeated alongside the active executor.

The following documented boundaries were retained rather than reported as defects:

- Passive READ identifies access to a validated inode with unknown PID. It does not establish which marker bytes were consumed, exact read count, semantic use or process intent. Kernel coalescing and mmap blind spots remain explicit.
- Startup and shutdown are observation gaps. Content validation occurs before every watch is installed; runtime checks inspect metadata rather than rereading marker content. Modifications, replacement, missing paths, overflow and failures invalidate coverage until an explicit restart.
- Ready denotes completed lifecycle setup. Zero or incomplete coverage is represented by watch counts and durable health evidence. Custom sinks can block; an unresponsive worker is surfaced by the documented stop timeout.
- Cooperative attribution identifies the current caller. Tool events describe invocation input attempts, including unsuccessful invocations. Filesystem copy completion and event persistence are separate boundaries; sink failure after a completed copy can leave the copy in place while surfacing an error.
- Same-account hostile mutation, system-wide enforcement and Phase 3 network/model parsing are outside this review. No exploit reproduction, external probe or transmission was performed.

---

_Reviewer: foundation_review_astra (gsd-code-reviewer)_  
_Depth: deep_
