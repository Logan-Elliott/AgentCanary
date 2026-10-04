# Phase 4 plan review

Date: 2026-10-03
Scope: bounded pre-execution review of `04-01-PLAN.md`, followed by one revision check. Static plan and interface analysis only; no application or test suite was run for this review.

## VERIFICATION PASSED

**Phase:** End-to-end demo and adversarial integration
**Plans verified:** 1
**Status:** All applicable checks passed; no open issues.

The revised plan covers a real child using the SDK, an actual tool invocation, real loopback HTTP, correlated durable evidence and observable failure cleanup. Both roadmap requirements are claimed in frontmatter and have implementing tasks.

## Coverage summary

| Requirement | Plans / tasks | Status |
| --- | --- | --- |
| E2E-01: complete local synthetic lifecycle | 04-01 / Task 1 | Covered: issued ID/run correlation, real child/tool, passive read, model input, blocked HTTP and retained reports |
| E2E-02: integration and failure boundaries | 04-01 / Task 2 and phase verification | Covered: multiple markers/runs, concurrent sources, readiness, child failure/timeout, descendant termination, reporting and existing regression coverage |

The relevant PROJECT.md requirements are represented. Clean wheel/sdist installation and full release documentation remain Phase 5 work as recorded in CONTEXT.md.

## Plan summary

| Plan | Tasks | Declared scope | Wave | Status |
| --- | --- | --- | --- | --- |
| 04-01 | 2 | 5 concrete implementation/test/document files and phase evidence documents | 1 | Valid |

`query verify.plan-structure` on the revised plan returned `valid: true`, no errors, no warnings, and files/action/verify/done present for both automatic tasks. `must_haves` was parsed and describes observable behavior supported by the runner and acceptance tests.

## Resolved revision findings

These are historical findings, not current issues.

| Prior severity | Required property | Revised evidence | Disposition |
| --- | --- | --- | --- |
| BLOCKER | Every automatic task declares the concrete files it creates or changes. | Both tasks now contain file assignments naming their implementation, test and documentation artifacts. | Resolved |
| BLOCKER | Verification returns failure if any required test, lint, format or type check fails. | Automated blocks now use literal `&&` conjunctions and the required RTK wrapper; phase verification also explicitly requires checking each exit status separately and success from every command. | Resolved |
| WARNING | Failure verification accounts for every owned process, including the tool beneath the simulated agent. | Phase verification requires a dedicated child process group/session, cleanup on timeout/interruption/failure and a bounded regression proving descendants do not survive. | Resolved |

The final bounded recheck confirmed literal runnable conjunctions, RTK wrapping for every verification command and removal of the unspecified examples directory. The structure validator still reports no errors or warnings.

## Remaining dimensions

- **Dependencies and coupling:** `03-01` exists and has a completed summary providing the required APIs. It is the earlier phase prerequisite. There is one local Phase 4 wave; no intra-phase cycle, same-wave pair, temporal coupling or incompatible transformation exists.
- **Wiring and contracts:** Actions connect the runner, CLI, SDK, monitors, listener and reports through issued ID and run correlation. The checked `Store`, `Observer`, `InotifyMonitor`, `BlockingProxy` and `render_report` interfaces support the composition. The plan requires durable evidence as well as HTTP rejection, which avoids mistaking 403 alone for successful detection.
- **Context compliance:** The plan retains the new-directory boundary, common run, seed-before-monitor ordering, real child/tool, local traffic, source-specific PID claims, bounded readiness and cleanup, safe evidence export and incomplete-chain failure. Ordered direct SDK observations, the independent passive-read predicate, JSONL export and explicit report instructions remain the recorded acceptance details in CONTEXT.md. No locked decision is reduced or deferred idea introduced.
- **Existing test coverage:** Task 2's full regression includes matching negative controls and HTTP rejection/no-forwarding tests already present. `test_field_boundaries_negative_controls_and_dedup`, framing rejections and `test_real_http_proxy_never_resolves_or_connects_upstream` support reuse instead of duplicate tests.
- **Scope:** Two tasks and five implementation/test/document files fit the plan budget. No estimate block is supplied.
- **Research resolution:** No unresolved research questions. The completed Phase 3 summary grounds the expected interfaces. No conflicting numeric claim was used as an acceptance assertion.
- **Dimension 7c:** SKIPPED (no Architectural Responsibility Map).
- **Dimension 8:** SKIPPED (`workflow.nyquist_validation` is false; no Validation Architecture section). No failing-direction or verify-path probe was supplied, so those probe-only checks remain silent.
- **Dimension 10:** SKIPPED for an on-disk project AGENTS.md (none found). User-supplied VM, identity, RTK and local-only instructions apply; no external action is planned.
- **Dimension 12:** SKIPPED (no PATTERNS.md). No project-local skills or agent-skills config mapping was found.
- **Review incorporation:** No external REVIEWS.md was supplied. All findings from this bounded review were addressed in the revised executable plan.

## Structured issues

```yaml
issues: []
```

The revised Phase 4 plan is ready for execution. Implementation verification remains necessary after execution; this review does not claim the demonstration has already passed.
