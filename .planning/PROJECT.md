# AgentCanary

## What This Is

AgentCanary is a Python-first local canary and tripwire framework for AI-agent workspaces. It creates unmistakably synthetic secret-like artifacts and correlates observed creation, reads, propagation, tool/model input and attempted HTTP transmission. Intended users are AI security engineers and developers evaluating their own agent sandboxes.

## Core Value

A canary is traceable from creation through observed access and propagation to attempted exfiltration, with evidence provenance and honest attribution limits.

## Current State

Version 0.1.0 is implemented, reviewed and verified locally. Milestone v0.1 comprises five completed phases, five plans and 13 tasks, with all 15 requirements satisfied and archived. No external publication has occurred.

The stdlib-only runtime contains 17 Python modules (3,298 lines); 19 Python test files contain 2,986 lines. All 220 tests pass on CPython 3.11.17, 3.12.3 and 3.14.8. Ruff and strict mypy pass. Final wheel/source artifacts each pass fresh installation, CLI/sensor/report checks and the complete demo on all three interpreters. CI includes Python 3.13 but has not run remotely. Counts describe the verified release source, not a coverage percentage.

## Requirements

### Validated

- ✓ Eight unique invalid synthetic artifact types, realistic/minimal profiles and safe inert custom templates — v0.1 (CORE-01, CORE-02).
- ✓ Durable structured events, atomic registry/CREATE transactions, installable typed CLI/SDK, text/JSON/JSONL reports and extension protocols — v0.1 (CORE-03, CORE-04).
- ✓ Unprivileged Linux reads, cooperative read/copy/tool/model/embedding observations, explicit attribution and tested concurrency/lifecycle failures — v0.1 (OBS-01–03).
- ✓ Local blocking HTTP inspection, model routes, bounded common representations and strict retained allowlist/ignore annotations — v0.1 (NET-01–03).
- ✓ Real child/tool/mock-model/HTTP propagation demo and major failure/edge-case integration tests — v0.1 (E2E-01, E2E-02).
- ✓ Clean installation and quality gates, professional docs/examples/license, independent review/fixes, cross-phase audit and local milestone archive — v0.1 (REL-01–03).

### Active

None. The requested local release is complete; a future milestone requires a new objective.

### Out of Scope

- Real credentials, live provider calls, remote collectors, telemetry and external deployment.
- Transparent system-wide TLS decryption and universal process attribution without cooperation or privileges.
- Privileged auditd/eBPF backends; public Monitor/EventSink contracts permit later adapters.
- Enforcement against a hostile process controlling the monitoring account. Local observations are not a sandbox or tamper-resistant evidence service.

## Context

The repository is a Linux/Python src-layout package with a committed development lockfile, MIT license, bounded CI definition, documentation and a reproducible installation verifier. Independent reviews found and corrected defects in state safety, monitor lifecycle, argument consistency, request identity, report publication, process ownership and optional SQLite sidecar turnover. No unresolved material finding or accepted verification override remains.

The retained ignored `agentcanary-demo-final` directory contains a completed six-action chain and two blocked loopback requests. Reproducible acceptance is in the tests and installation verifier; the local output is supplementary evidence. Full phase records, audit and requirements are under `.planning/milestones/`.

## Constraints

- Keep artifacts, services, fixtures and changes in this Linux VM; no host/shared mounts.
- No remote push, PR, publishing, deployment or messaging without later explicit authorization.
- Synthetic fixtures and loopback application traffic only; no provider credentials or cloud accounts.
- At most two heavy builds/test workers at once; preserve unrelated existing work.
- Every new commit uses Logan-Elliott <dev.loganelliott@gmail.com>.
- New delegated agents use gpt-6-astra with xhigh reasoning; routine decisions and local lifecycle were delegated by the user.

## Key Decisions

| Decision | Rationale | Outcome |
| --- | --- | --- |
| Python >=3.11, src package, stdlib runtime | Small runtime dependency surface and typed reusable CLI/SDK | ✓ Verified on three interpreters and clean distributions |
| SQLite WAL/FULL with independent operation connections | Atomic registry/event batches, concurrent writers and durable ingestion order | ✓ Verified, including bounded sidecar deletion revalidation |
| Exclusive no-follow creation and complete preflight | Preserve existing files and avoid unsafe selected paths | ✓ Verified ordinary failure rollback; crash boundary documented |
| Mandatory invalid markers and inert custom templates | Traceable synthetic artifacts without functional credentials or template execution | ✓ Eight built-ins and custom templates verified |
| Separate passive, cooperative SDK and HTTP evidence | Never invent PID, semantic consumption or authenticated causal identity | ✓ Unknown passive/HTTP PID and caller SDK PID checked |
| Explicit registry refresh and conservative watch invalidation | Avoid pretending changed artifacts retain proven coverage | ✓ Health, snapshot and failure paths verified |
| Immutable argv snapshot before tool observation/spawn | Make observed invocation agree with executed arguments | ✓ Mutation regression verified |
| Loopback-only endpoint that always blocks | Observe attempts without forwarding or external collector dependency | ✓ All ten model routes and no-upstream behavior verified |
| Bounded decoding and strict retained policy | Control resource use and preserve audit history despite ignore/allowlist matches | ✓ Limits, diagnostics and exact identity checks verified |
| Pre-TLS SDK model/HTTP/embedding hooks | Support cooperating model integrations without decryption claims | ✓ Input attribution and limits documented/tested |
| Isolated demo with child-only subreaper | Reap controlled descendants without changing caller-wide child ownership | ✓ Real failure/signal paths verified |
| Synchronize before exclusive report publication | Prevent failed finalization from claiming successful completion | ✓ Dedicated publication regressions verified |
| Keep leader unreaped until group signals finish | Preserve process identity ownership throughout cleanup | ✓ Mocked ordering and real lifecycle checks verified |
| Independent review and clean installation gate | Catch failures beyond unit-level happy paths | ✓ Three final defects corrected; zero open findings |
| Local milestone completion only | Respect VM boundary and explicit remote shipping restriction | ✓ Archive and local tag; no external ship action |

---
Last updated: 2026-10-03 America/New_York after local v0.1 completion (2026-10-04 UTC).
