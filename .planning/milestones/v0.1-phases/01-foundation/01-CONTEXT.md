# Phase 1: Foundation and safe canary lifecycle - Context

Gathered: 2026-10-03
Status: Ready for planning

## Phase Boundary
Implement package, core models, SQLite event/registry storage, synthetic templates, safe creation/seeding, reports and initial CLI. Monitoring and network adapters are later phases.

## Implementation Decisions
- Python >=3.11, src layout, argparse CLI; no mandatory third-party runtime dependencies unless justified.
- Event actions CREATE, READ, COPY, TOOL_USE, MODEL_REQUEST, EXFILTRATION plus monitor health. UUID canary/event IDs, UTC timestamps, optional run ID and PID, source/provenance, destination and bounded metadata. SQLite assigns ingestion sequence. EventSink and Monitor protocols allow future adapters.
- Stable marker AGENTCANARY_SYNTHETIC_<random ID> with at least 128 bits entropy; every credential-like value contains the unique token. No real SSH keypair or valid provider credential syntax. Reserved .invalid hosts.
- Built-ins: aws-key, openai-key, anthropic-key, kubeconfig, ssh-key, env, database, payroll. Custom plain text string.Template substitution, no executable templates.
- Explicit state directory defaults .agentcanary in current directory; --state-dir may appear before subcommand; document consistent UX. Event reports do not expose token values or file contents by default.
- Seed safe relative paths, protect preexisting files and all symlink components, O_EXCL restrictive 0600 files, state dir 0700. Preflight multi-file seeding and rollback newly created files on routine failures; no claim of cross-filesystem transactional durability.
- User delegates all routine choices. No approval checkpoint needed. Local commits only, fixed author identity.

## Existing Code Insights
Greenfield. .planning/PROJECT.md and research describe the evidence contract.

## Deferred Ideas
Monitoring, networking, full demo and final documentation belong to subsequent phases.
