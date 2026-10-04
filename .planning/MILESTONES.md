# Project Milestones: AgentCanary

## v0.1 Local release (Completed locally: 2026-10-03)

**Delivered:** AgentCanary 0.1.0 traces synthetic canaries from creation through access, tool/model propagation and attempted HTTP transmission, with local evidence and explicit attribution boundaries.

**Phases completed:** 1–5; five plans, 13 tasks, 15 requirements. **Closeout:** verified_closeout. **Open findings / verification overrides:** zero / zero.

### Accomplishments

- Eight invalid synthetic artifact types, custom templates and safe workspace seeding paired with atomic CREATE records.
- Real Linux access notifications and attributed SDK read/copy/tool/model/embedding observations.
- Bounded local HTTP inspection that always blocks, with retained strict policy annotations and text/JSON/JSONL reports.
- Real installed child/tool/mock-model/HTTP demo, reliable retained evidence and tested failure cleanup.
- Reviewed release package, professional documentation and examples, reproducible clean-install checks and local milestone archive.

### Verification

220 tests pass without skips on CPython 3.11.17, 3.12.3 and 3.14.8. Ruff lint/format and strict mypy pass. Final wheel and source archive each pass clean installation and complete installed CLI/demo checks on all three interpreters: six fresh installations. Hosted CI and Python 3.13 local execution are not claimed.

Independent source review is clean after corrections, including final report publication, process ownership and SQLite sidecar deletion races. Independent integration audit verifies 14/14 connections, 13/13 flows, ten model routes and all 15 requirements, with no BLOCKERs or WARNINGs. Ten extra audit tests and benign adapter/route checks passed; both distributions match all 17 source modules.

### Archive and statistics

- [Roadmap](milestones/v0.1-ROADMAP.md), [requirements](milestones/v0.1-REQUIREMENTS.md), [milestone audit](milestones/v0.1-MILESTONE-AUDIT.md) and all five [phase directories](milestones/v0.1-phases/) archived locally by the GSD finalizer.
- 17 runtime modules / 3,298 lines; 19 Python test files / 2,986 lines. These are source counts, not coverage measurements.
- 102 tracked files changed and 37 commits between initial checkout `a304952` and verified checkpoint `4d0a116`, before archive/state bookkeeping. Project initialization `fce02a6` and verified checkpoint are both dated 2026-10-03 America/New_York.
- Thirteen tasks counted from actual plan XML (3+3+3+2+2); the GSD archiver reported zero because its summary parser did not count the compact task metadata. This entry corrects that derived statistic without changing execution records.
- Retained local demo: `agentcanary-demo-final/report.txt`; six actions and two HTTP 403 responses. This ignored output is supplemental to reproducible automated acceptance.

### Boundaries and next work

Linux/proc and explicit observation integrations are required. Passive/HTTP PID is unknown; encrypted or bypassing traffic and same-account tampering remain disclosed limits. No unresolved implementation work or accepted technical debt remains in this milestone. Optional auditd/eBPF and opt-in TLS integration are future scope, not promised release capabilities.

Project complete for the authorized local scope. The current branch is preserved and local tag `v0.1` identifies the completed milestone. No push, PR, package publication or deployment occurred.
