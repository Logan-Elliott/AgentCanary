---
phase: 05-release
plan: 01
subsystem: release
tags: [packaging, documentation, review, regression, installation]
requires:
  - phase: 04-integration
    provides: Installed simulated-agent lifecycle demonstration and failure tests
provides:
  - Verified wheel/source distributions and reproducible isolated installation checker
  - Professional local release documentation and pinned CI workflow definition
  - Independently reviewed corrections and multi-interpreter release evidence
affects: [milestone-audit]
requirements-completed: [REL-01, REL-02, REL-03]
one_liner: "AgentCanary installs cleanly, passes 220 tests on three Python versions, and completes the reviewed local canary chain."
key-decisions:
  - "No runtime dependency or external service is required; source builds may download the declared backend."
  - "Report publication follows synchronization; process-group signals precede final child reaping."
  - "Only safe disappearing SQLite sidecars receive bounded revalidation; primary state protection remains strict."
  - "Milestone audit and archival are local administrative closeout; no remote release is authorized."
actuals:
  tasks: 2
completed: 2026-10-04
status: complete
---

# Phase 5 Plan 1: Release hardening and documentation

**AgentCanary 0.1.0 passes local release acceptance with no outstanding independent review findings.**

## Accomplishments

- Completed package/license metadata, wheel/source contents, typed package distribution, source examples/docs/tests and `scripts/verify_install.py`.
- Added concise README, architecture, threat model, coverage limits, integration examples, contribution/security guidance and release notes. CI defines bounded Python 3.11–3.14 jobs using pinned action commits; no hosted execution is claimed.
- Completed independent review across architecture, false positives/negatives, process attribution, concurrency, synthetic-data handling, network gaps, portability, testing and usability, reusing resolved Phase 1–3 deep reviews.
- Fixed final-summary publication and process-group ownership defects, then a real SQLite sidecar deletion race found during release regression. Added 36 dedicated correction regressions and retained original review evidence.
- Verified all 220 tests on Python 3.11.17, 3.12.3 and 3.14.8, strict typing, lint/format, final build and six fresh wheel/source installations. Every installation runs the CLI and full demo outside the checkout.

## Task commits

1. Package/documentation polish — `2a0cdc6`, with documentation updates in `74985ca` and `16efd8c`.
2. Independent review and release acceptance — source corrections `20c7d36` and `f1bae7a`; review, acceptance and verification artifacts accompany phase closure.

Every new commit uses Logan-Elliott <dev.loganelliott@gmail.com>. Preexisting local execution tooling is excluded from project commits.

## Verification

See `05-ACCEPTANCE.md` for actual commands, interpreter versions, durations, distribution checks and the retained demo identifiers. Full-suite results are 220 passed without skips on each interpreter; strict mypy covers 17 modules; Ruff passes. Final source is `f1bae7a`. Independent reviewer correction checks passed 10 demo tests and 26 sidecar tests.

`agentcanary-demo-final/report.txt` preserves CREATE → READ → COPY → TOOL_USE → MODEL_REQUEST → EXFILTRATION with two blocked loopback HTTP requests. A separate actual tool receipt and copied-byte digest verify propagation; source-specific PID limitations remain explicit.

## Deviations and resolved findings

Review-driven source changes are within the planned hardening task. CR-01/02 fix completion evidence and process identity ownership; CR-03 fixes concurrent optional sidecar deletion without relaxing unsafe-file rejection. `05-STORE-RACE.md` records reproduction of the ordinary scheduling race and deterministic regression coverage. No finding is accepted as unresolved debt.

## Requirements and lifecycle handoff

REL-01 and REL-02 have executable installation/quality evidence and complete documentation. REL-03's review/fix/rerun work is verified here. Its administrative milestone audit, archive and cleanup follow this verified phase as the enclosing GSD lifecycle; archival completion is recorded in MILESTONES.md, not asserted to have happened before this handoff.

## Boundaries

Linux/proc support, unknown passive/HTTP PID, explicit integration coverage, bounded decoders, absence of transparent TLS inspection and same-account tampering limitations are documented. No external publication, CI run, provider call or universal containment claim is made.

## Self-check

All planned code/docs/distribution files exist, source correction commits resolve, local acceptance passes and the independent report is clean. No skipped acceptance checks, stubs or unresolved implementation findings remain. Continue directly to milestone audit and local archival.
