# Phase 2: Filesystem and attributed observations - Context

Gathered: 2026-10-03
Status: Ready for planning

## Phase Boundary
Detect real reads of registered artifacts on Linux and provide cooperative SDK read/copy/tool observations. Build reusable issued-token matching for phase 3. No transparent instrumentation or invented process attribution.

## Implementation Decisions
- Monitor registered artifacts inside the selected workspace, not arbitrary host files. Seed before monitoring; explicitly report the monitored snapshot and any missing or altered artifact. Use Linux inotify without privileges (stdlib ctypes or small adapter).
- Validate registered file digest before attaching watches without self-generated READ evidence. Avoid scanning watched files and reporting monitor reads as agent reads.
- Handle IN_ACCESS, watch invalidation, deletion/replacement, queue overflow, clean start/stop and errors. An altered or replaced artifact must not cause a false canary read. If rearming cannot be made reliable, invalidate coverage with durable health evidence and require restart. Document all windows.
- Never guess a PID from /proc. Filesystem READ events have pid=None and explicit kernel-notification provenance. SDK events use actual caller PID plus run ID. Claims describe observed access or passed input, not proof of semantic use.
- Public Observer-style SDK: instrumented read, safe copy, observe_tool/tool invocation, generic observe(action,payload) for later model/network integration. Existing Event/Store interfaces are in phase1 SUMMARY. Match exact registered marker strings, not generic secret patterns. Bound scanned input with explicit diagnostic behavior.
- Tool wrapper uses argument arrays, shell=False, explicit stdin and timeout; never records argv, environment, payload or raw subprocess output. No execution occurs automatically from artifact content.
- CLI monitor WORKSPACE with optional duration, run-id and flushed readiness output; Ctrl-C shuts down and preserves evidence. New additions require explicit refresh/restart if using snapshot design.
- User delegates all routine choices and gap fixing. All spawned agents are Astra xhigh. Tests only inside local fixtures.

## Existing Code Insights
Frozen Canary includes path and content sha256. EventSink.record(Event)->Event and Store.canaries() exist. Event metadata keys must be extended deliberately. Core is Linux-first and uses safe no-follow path helpers. Templates and report formats are already tested.

## Deferred Ideas
Encoded HTTP/model matching and configuration belong to Phase 3. Privileged auditd/eBPF implementations remain future adapters.
