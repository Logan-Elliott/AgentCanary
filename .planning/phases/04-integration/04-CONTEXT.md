# Phase 4: End-to-end demo and integration — Context

Status: Ready for planning. Routine choices are delegated by the user.

## Boundary and decisions

- Supply `agentcanary demo --directory PATH [--json]` as a reproducible installed-package demonstration. Require a new output directory (or safely create a unique default); never overwrite an existing user directory. Keep workspace, private state and reports beneath it. Make errors and output locations clear.
- Seed before starting monitors. Start inotify and the loopback blocking endpoint and verify readiness before starting a real Python child process simulating an agent. The child uses the installed package and an explicit common run ID.
- The child reads the canary, copies it, passes it to a real local subprocess tool, observes a mock model or embedding input, and submits synthetic content by HTTP to the blocking listener. An absolute `.invalid` destination in an HTTP request expresses attempted egress without resolving or connecting to that destination. All actual network traffic stays on loopback.
- Verify issued ID and run correlation, ordered direct SDK observations, child PID attribution, passive/HTTP unknown PID, and HTTP 403 rejection. Do not infer causal ordering between independently scheduled passive observations.
- Use bounded child execution, monitor health checks, deterministic shutdown, and readiness/event predicates instead of timing assumptions. Fail the command if the expected chain or passive read is missing. Preserve useful failure evidence without silently declaring success.
- Export a readable summary and JSONL evidence without artifact contents/token values. Include the report command for inspecting retained state. The demonstration is a useful public acceptance test, not a second implementation of monitoring.
- Expand realistic integration/failure coverage where existing tests leave gaps: multiple issued canaries, concurrent event sources, readiness, child failure/timeout, no forwarding, report round trip and cleanup. Unit edge cases already covered should not be duplicated without reason.

## Existing interfaces

Use Phase 3 SUMMARY and source as authority: Store, Observer, InotifyMonitor, BlockingProxy, policy/report APIs. Public extension contracts stay unchanged. CLI demo dispatch must be explicit rather than falling through to seed. No cloud SDK or credentials are needed.

## Deferred

Release metadata, CI, clean wheel/sdist installation, full documentation reconciliation and final cross-phase review belong to Phase 5.
