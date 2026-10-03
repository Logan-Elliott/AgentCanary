# AgentCanary

## What This Is

AgentCanary is a Python-first, local canary and tripwire framework for AI-agent workspaces. It plants unmistakably synthetic secret-like artifacts and correlates their creation, access, propagation, model-request inclusion, and attempted HTTP transmission. Intended users are AI security engineers and developers evaluating their own agent sandboxes.

## Core Value

A canary must be traceable from creation through observed access and propagation to attempted exfiltration, with evidence provenance and honest attribution limits.

## Requirements

### Validated

None yet; implementation and local verification pending.

### Active

- [ ] Safe unique canary generation and workspace seeding, including custom templates.
- [ ] Durable structured events, local reports, filters, and extension interfaces.
- [ ] Unprivileged Linux filesystem access monitoring and practical process/tool attribution.
- [ ] HTTP inspection and detection in model/API requests.
- [ ] Reliable isolated simulated-agent demo, realistic tests, and clean installation.
- [ ] Professional documentation, threat model, limitations, and final review.

### Out of Scope

- Real credentials, live provider calls, remote collectors, telemetry, and external deployment.
- Transparent system-wide TLS decryption and universal process attribution without cooperation or privileges.
- Privileged auditd/eBPF backends in this release; extension interfaces must permit them later.
- Enforcement against a hostile process with control of the monitoring account; this is an observation tool, not a sandbox.

## Context

Greenfield repository with a placeholder README. Python 3.12 is installed on an isolated Linux VM with 4 CPUs and 8 GiB RAM. The user delegated routine design and acceptance decisions, all phases, debugging, review, and local release verification. GSD Core is active; the archived GSD Pi runtime is retired.

## Constraints

- Keep artifacts, services, fixtures and changes within this VM. Never access host/shared mounts.
- No remote pushes, PRs, publishing, deployments, or messages without later explicit authorization.
- All test traffic stays on loopback; synthetic data only. No cloud accounts or real credentials.
- At most two heavy builds/browser workers at once; project-local dependencies and committed lockfile.
- Every new commit uses Logan-Elliott <dev.loganelliott@gmail.com>.

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Python >=3.11, src package, stdlib-first runtime | Maintainable, installable CLI/SDK with a small dependency surface | Pending verification |
| SQLite event and canary registry | Atomic creation/events, multiprocess concurrency, local querying | Pending verification |
| Separate filesystem, cooperative SDK and HTTP inspection evidence | Linux inotify has no PID; attribution must never be invented | Accepted |
| Explicit loopback HTTP inspection, block by default | Detect real attempted requests without an external service or forwarding synthetic artifacts | Accepted |
| SDK observation before TLS | Provide model/tool attribution with explicit integration and documented blind spots | Accepted |
| Autonomous routine decisions and gap closure | Explicit user delegation; no repeated phase approvals | Accepted |
| Local milestone completion only | VM policy prohibits external ship actions | Accepted |

## Evolution

Update validated requirements, decisions, risks, and next steps at each verified phase transition. Review all sections at milestone completion. Preserve resumable state and concrete verification evidence.

---
Last updated: 2026-10-03 after initialization.
