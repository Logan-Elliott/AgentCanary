# Project Retrospective

## Milestone: v0.1 — Local release

**Completed locally:** 2026-10-03 America/New_York (2026-10-04 UTC). **Phases:** 5. **Plans:** 5. **Tasks:** 13.

### What was built

- Typed stdlib-only Python CLI/SDK, eight synthetic canary types, inert custom templates, safe seeding and durable event reports.
- Linux passive reads, cooperative process-attributed observations and a bounded blocking HTTP endpoint with strict retained policy.
- Real child/tool/model-input/loopback demo, independently reviewed failure cleanup and reproducible clean distribution acceptance.

### What worked

- Small shared record/sink/monitor contracts let each adapter preserve distinct evidence and attribution semantics.
- Real process, file-notification and socket integration exposed failures that isolated happy-path tests missed.
- Independent reviews found material publication, process ownership and concurrency defects before completion; each correction gained focused regression evidence.
- Fresh wheel and source installs outside the checkout caught packaging/import boundaries while retaining zero runtime dependencies.
- Explicit local-only scope, synthetic fixtures and no-forwarding design kept acceptance independent of credentials or provider services.

### What was inefficient

- GSD derived state sometimes retained old phase/progress values, and the archiver did not recognize task counts from compact summaries. Canonical verification was checked and state/statistics reconciled from actual artifacts.
- A late full-suite scheduling failure required another compatibility and distribution pass. The resulting deterministic zero-link sidecar regressions now complement real stress coverage.
- Whole-suite checks across interpreters are relatively expensive in this four-CPU VM. Sequential suites and no more than two heavy workers kept their results interpretable.

### Patterns established

- Source, provenance and unknown PID are first-class data; correlation labels never imply authenticated identity or cross-sensor causality.
- Coverage loss is recorded explicitly. Ready, observed input and blocked attempt remain separate from full coverage, semantic use and delivery.
- Publish completed evidence only after its contents are synchronized. Preserve exclusive creation and unrelated destinations on failure.
- Retain process identity ownership until the last group signal; only then reap the leader.
- Handle disappearing optional SQLite sidecars with a narrow bounded retry, preserving all primary-file, ownership, type, link and permission checks.
- Treat independently rerun checks and reported earlier evidence separately in reviews and audits.

### Key lessons

1. Exercise concurrent connection turnover, not just simultaneous inserts; ordinary cleanup can race with file validation.
2. A successful write syscall is not finalized evidence. Test failures at synchronization and publication boundaries.
3. Process-group creation alone does not guarantee later numeric identity ownership. Verify cleanup order as well as eventual child disappearance.
4. Installed entry points, subprocess module imports and package source archives need actual clean-environment checks.
5. Document unsupported encrypted/bypassing traffic and passive attribution limits as operational boundaries, and keep them visible in event provenance.

### Cost observations

New delegated agents used Astra at xhigh after user steering. Exact session/model token totals were not measured; diff-size estimates in early execution records are not billing measurements. Independent narrow reviews avoided repeatedly running the full suite. The final acceptance ran 220 tests on each of three interpreters plus six fresh installations; no coverage percentage is claimed.

## Cross-milestone trends

Only one milestone exists, so no cross-milestone trend is established yet.

| Milestone | Phases / plans | Automated acceptance | Review outcome |
| --- | --- | --- | --- |
| v0.1 | 5 / 5 | 220 tests on three interpreters; six fresh installs; lint, format, strict typing and build | All material findings corrected; no verification overrides |

## Cleanup record

All completed milestones have phase archives. `.planning/phases/` is empty and `.planning/quick/` is absent; no further phase/quick archival is necessary. The branch and unrelated local tooling are preserved. No remote fetch/prune, push, PR, publication or deployment was performed.
