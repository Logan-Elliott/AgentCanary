---
phase: 02-observations
plan: 01
subsystem: observations
tags: [python, linux, inotify, sdk, process-attribution]
requires:
  - phase: 01-foundation
    provides: Immutable canary/event records, safe filesystem helpers and durable Store
provides:
  - Bounded exact issued-marker matching with explicit registry refresh
  - Cooperative read, exclusive copy, tool input and generic model/network observations
  - Unprivileged Linux snapshots with coverage health and reliable lifecycle
  - CLI monitor with flushed readiness, duration and signal cleanup
affects: [03-network, 04-integration, 05-release]
tech-stack:
  added: []
  patterns: [ctypes-inotify, explicit-registry-snapshots, caller-pid-attribution, conservative-watch-invalidation]
key-files:
  created: [src/agentcanary/matching.py, src/agentcanary/sdk.py, src/agentcanary/monitors/__init__.py, src/agentcanary/monitors/inotify.py, tests/test_observer.py, tests/test_monitor.py, tests/test_observation_failures.py]
  modified: [src/agentcanary/__init__.py, src/agentcanary/cli.py]
key-decisions:
  - "Passive reads identify an unchanged registered inode with pid=None; SDK PID always identifies the caller."
  - "Monitor start validates all content before installing any watch; changes invalidate coverage until explicit stop/start."
  - "Observer.refresh explicitly replaces the marker registry snapshot; input beyond its byte bound fails with durable health evidence."
  - "Tool events distinguish supplied input from invocation attempts; shell=False, explicit arguments, timeout and discarded output."
requirements-completed: [OBS-01, OBS-02, OBS-03]
coverage:
  - id: D1
    description: Real subprocess reads produce passive evidence without invented PID or self-read feedback
    requirement: OBS-01
    verification:
      - kind: integration
        ref: tests/test_monitor.py#test_real_subprocess_read_without_self_access
        status: pass
    human_judgment: false
  - id: D2
    description: SDK read, copy, tool and generic model inputs match issued markers and preserve caller/run correlation
    requirement: OBS-02
    verification:
      - kind: integration
        ref: tests/test_observer.py
        status: pass
    human_judgment: false
  - id: D3
    description: Concurrent processes, replacement, overflow, startup/worker/sink failure and shutdown preserve honest evidence
    requirement: OBS-03
    verification:
      - kind: integration
        ref: tests/test_monitor.py and tests/test_observation_failures.py
        status: pass
    human_judgment: false
actuals:
  tokens: 14243
  tasks: 3
  commits: 6
commits: 6
plan_head_before: 729af227c526d0a51b100e244081fc82721aa000
plan_head_after: 25f3e2044034998c4be08c1bacbae01952503c96
duration: 30min
completed: 2026-10-03
status: complete
---

# Phase 2 Plan 1: Filesystem and attributed observations Summary

**Validated Linux inode snapshots detect real reads, while the cooperative SDK records exact marker propagation with caller PID and run correlation.**

## Accomplishments

- Added bounded bytes/text marker matching, per-call deduplication and explicit registry refresh. A complete issued token embedded in arbitrary surrounding data, including hexadecimal suffixes, remains a match. Unknown and partial markers do not match.
- Added safe regular-file reads and exclusive, private copies without following selected symlinks. COPY evidence follows successful write/fsync; failed writes remove only the newly created inode. Relocated content remains attributable to its registered canary.
- Added supplied tool-input and invocation-attempt evidence. The wrapper executes only an explicitly supplied argument array, passes explicit stdin, enforces a timeout, discards subprocess output, and records neither argv nor environment nor raw payloads.
- Added stdlib-only Linux inotify. All validation reads occur before all watches, and watches attach through verified file descriptors. Subsequent identity checks inspect metadata without reading content. Modification, deletion, replacement, ancestor movement, overflow and failures report lost coverage.
- Added monitor CLI readiness, finite duration, SIGTERM and Ctrl-C teardown while preserving create KIND, seed ROOT and report behavior.

## Task Commits

1. Registered-token matcher and attributed SDK — `3df1de3`.
2. Linux snapshot monitor and CLI — `af627bd`.
3. Concurrent process and failure verification — `25f3e20`.

Measured Git span is **6 commits**, because root-agent commits `37e5808`, `d4302e7` and `5c905f2` landed on the shared branch between the persisted base and final task HEAD. Those commits belong to foundation review/threat documentation; the task table lists this executor's three commits. The realized-diff token estimate covers this phase's nine code/test files only. All commits use Logan-Elliott <dev.loganelliott@gmail.com>.

## Public API for Phase 3

All types below are top-level `agentcanary` exports. Existing Store/Event contracts are unchanged and no metadata allowlist extensions were needed.

```python
TokenMatcher(canaries: Iterable[Canary], *, max_bytes: int = 1048576)
TokenMatcher.match(payload: bytes | str) -> MatchResult
# MatchResult.canaries: tuple[Canary, ...]; .bytes_scanned: int
# PayloadTooLarge: ValueError; byte limit 1..16 MiB; no partial scan is accepted.

Observer(store: Store, *, run_id: str | None = None,
         sink: EventSink | None = None, max_bytes: int = 1048576)
Observer.refresh() -> None
Observer.read(path: str | Path) -> bytes
Observer.copy(source: str | Path, destination: str | Path) -> tuple[Event, ...]
Observer.observe(action: Action, payload: bytes | str, *,
                 destination: str | None = None,
                 metadata: Mapping[str, Scalar] | None = None,
                 provenance: str = "sdk_input") -> tuple[Event, ...]
Observer.observe_tool(payload: bytes | str, *, tool: str) -> tuple[Event, ...]
Observer.run_tool(argv: Sequence[str], *, input: bytes | str | None = None,
                  tool: str = "subprocess", timeout: float = 30.0) -> ToolResult
# ToolResult.returncode: int; .events: tuple[Event, ...]
# ToolInvocationError: RuntimeError for spawn/timeout failures; no raw argv included.

InotifyMonitor(store: Store, root: str | Path, *, run_id: str | None = None,
               sink: EventSink | None = None)
InotifyMonitor.start() -> None  # synchronous snapshot setup, returns when ready
InotifyMonitor.stop() -> None   # joins worker, closes descriptors; idempotent if healthy
InotifyMonitor.check() -> None  # raises MonitorError after worker/sink failure
# Context manager supported; .ready is threading.Event
# .running: bool; .watch_count: int; .error: str | None
```

`Observer` and `InotifyMonitor` generate a run UUID if omitted. `Observer` takes a registry snapshot at construction; call `refresh()` after registering new canaries. Matcher replacement is synchronized and each observation uses one stable matcher. Passive monitoring takes a fresh snapshot only at start; use stop/start for new canaries or restored artifacts.

Generic `observe(Action.MODEL_REQUEST, payload, metadata={"model": "fixture"})` supports cooperative model/embedding input. EXFILTRATION can likewise be supplied by a trusted adapter. CREATE and MONITOR_HEALTH are reserved. The adapter must sanitize URL destinations and its operator labels before passing them; this is not a general credential scrubber. Metadata is still the core's reviewed scalar allowlist.

SDK observation events use `source="sdk"`, actual `os.getpid()` at observation time, `attribution="caller_pid"` and the configured run ID. Provenance is `sdk_read_completed`, `sdk_copy_completed`, `sdk_tool_input`, `sdk_tool_invocation_input`, or caller-specified/default `sdk_input`. Invocation input is recorded **before** spawning and may describe an unsuccessful attempt; it does not prove child consumption or successful semantic use. A nonzero exit is returned normally. Tool spawn/timeout failures add bounded health diagnostics then raise.

Passive READ uses `source="inotify"`, `provenance="kernel_inode_access"`, `pid=None`, and `confidence="validated_inode_access"`. Health uses `monitor_diagnostic` and bounded reason codes. Worker/sink exceptions are reduced to exception class names, surfaced through check/stop, and recorded if the sink remains writable.

CLI example:

```text
agentcanary --state-dir ./state monitor ./workspace --run-id demo --duration 30
```

The first stdout line is flushed JSON with `status="ready"`, `watch_count`, `run_id` and `registry_policy="snapshot_restart"`. Ready means lifecycle initialization completed; zero or incomplete coverage is represented by watch count and durable health events.

## Boundaries and Decisions

- Linux inotify reports access to an inode; notifications can coalesce and do not expose PID, byte ranges, read counts, or semantic intent. mmap and unsupported access paths remain blind spots. See the [Linux inotify manual](https://man7.org/linux/man-pages/man7/inotify.7.html).
- Startup validation and shutdown are observation gaps. Altered, missing, unsafe, out-of-root or over-1-MiB artifacts are not monitored. Restart validates again; changed registered digests continue to fail until restored or re-registered appropriately.
- Validation is never repeated while this monitor's watches are active. Running another independent monitor or content reader against watched inodes can produce ordinary passive access evidence; the kernel cannot identify its actor.
- Any content/metadata/identity change invalidates the inode permanently for that run. Accesses sharing a batch with invalidation are conservatively discarded. Metadata checks cannot make observation atomic with concurrent hostile changes; no enforcement guarantee is claimed.
- Queue overflow invalidates every watch, reports unknown dropped count as `-1`, and requires restart. No automatic rearm assumes a marker remains present.
- Copy destination parents must already exist. Filesystem side effects and evidence persistence are separate boundaries: a sink error after a completed copy leaves the successfully written file and surfaces the error.
- stop() gives a worker up to 10 seconds; an unresponsive custom sink is reported rather than falsely claiming the thread stopped. Normal and injected failing built-in paths are verified to release workers and descriptors.

## Verification

- `uv run pytest -q`: **83 passed**, no skips, 21.62 seconds.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed, 45 files.
- `uv run mypy src`: passed, 14 source files.
- Real child processes exercised reads, tool stdin, 48 concurrent SDK reads across three artifacts, and competing exclusive copies.
- Real CLI processes exercised readiness, duration, SIGTERM and Ctrl-C. Injected faults exercised queue overflow, malformed kernel records, mutation during startup, watch/thread/sink failures and copy disk failure.

## Deviations from Plan

No scope deviations. Root review corrected the first matcher draft's suffix boundary to preserve exact issued tokens embedded beside hexadecimal data; the regression is in the monitor task commit. Snapshot validation also explicitly checks marker presence in addition to registered digest, and unsupported platforms report the Linux requirement.

GSD state/roadmap/requirement handlers ran. As in Phase 1, the handlers retained an In Progress status despite verified completion and counted only currently materialized plans. Phase 2 status and the existing five-phase roadmap counters were normalized to 2/5 complete, preserving every later phase as pending.

## Threat Flags

The plan did not contain a formal threat register. Planned local file-access and process invocation surfaces are implemented with no-follow paths, regular-file checks, exclusive creation, bounded input, explicit argv, shell=False and discarded output; these are reviewed in `docs/threat-model.md`. No network endpoint, authentication path or schema trust boundary was added.

## Known Stubs

None. No skipped tests or unrun plan verification commands remain.

## Next Phase Readiness

Phase 3 can reuse TokenMatcher and generic Observer.observe for bounded network/model inspection. HTTP parsing, encoding transforms, URL sanitization and network policy remain Phase 3 responsibilities. No external service or credential setup is needed.

## Self-Check: PASSED

Verified all seven new source/test artifacts plus both phase documents exist; all three task commit hashes resolve to Git commits. The final suite and quality results are recorded above.
