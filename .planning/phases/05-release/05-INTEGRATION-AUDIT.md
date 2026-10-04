---
milestone: v0.1
phase: 05-release
audited: 2026-10-04T00:18:13Z
status: passed
implementation: f1bae7aa73ea155c8ab7e0271084b490e818bc06
repository_head: d520580
findings:
  blocker: 0
  warning: 0
wiring:
  expected: 14
  wired: 14
  broken: 0
  top_level_exports_reviewed: 29
  internally_consumed_exports: 28
  intentional_external_protocols: 1
  unintended_orphans: 0
api:
  model_routes_consumed: 10
  model_routes_orphaned: 0
flows:
  complete: 13
  broken: 0
requirements:
  mapped: 15
  wired: 15
  broken: 0
administrative_handoff: REL-03 milestone archive and state evolution follow this audit
---

# Integration Check Complete

**Verdict: PASSED for cross-phase product integration.** All 14 expected connections and 13 user/operational flows are wired. No outstanding BLOCKER or WARNING was identified. The release review/fix/rerun chain is verified; the enclosing milestone workflow must still perform the local archive and evolve PROJECT/state. This report does not claim that administrative transaction has already happened.

Scope covers Phases 1–5 at source `f1bae7a`, with phase metadata at `d520580`. The audit read every supplied project, requirement, roadmap, summary, verification, acceptance and final-review artifact, then traced current producers, consumers, return values, persistence and display. No project skills exist under `.codex/skills/` or `.agents/skills/`; the project has no configured `agent_skills`. Implementation and tests were not edited. Only this audit artifact was created; preexisting local tooling was preserved.

## Wiring Summary

**Connected:** 28 top-level exports have actual internal consumers, including returned record types whose fields are consumed without importing their class names. The remaining export, `Monitor`, is an intentional public structural protocol; its built-in compatibility and an external adapter lifecycle were independently exercised. All 29 exports are accounted for.

**Orphaned:** 0 unintended exports. **Missing:** 0 of 14 expected connections. The module APIs `render_report()` and `run_demo()` also have verified CLI/demo/install consumers.

### Phase provides/consumes map

| Phase | Provides from SUMMARY | Actual downstream consumers |
| --- | --- | --- |
| 1 — Foundation | Synthetic templates, safe seeding, immutable records, Store, reports, CLI and extension contracts | Phase 2 snapshots/read/copy/tool events; Phase 3 HTTP matching/policy; Phase 4 creation and evidence export; Phase 5 package/CLI acceptance |
| 2 — Observations | TokenMatcher, Observer, inotify lifecycle and diagnostics | Phase 3 encoded HTTP inspection and SDK pre-TLS helpers; Phase 4 real child and passive sensor; Phase 5 installed monitor and demo |
| 3 — Network | HTTPInspector, BlockingProxy, strict policy, retained annotations | Observer HTTP/model/embedding methods; CLI monitor/proxy/report; Phase 4 model/collector requests; Phase 5 installed endpoint acceptance |
| 4 — Integration | `run_demo`, installed child entry point, completion gate, retained reports and cleanup | CLI `demo`; installation verifier; release acceptance and documentation |
| 5 — Release | Distribution configuration, installation verifier, docs/examples and review corrections | Built wheel/sdist, executable installed CLI/demo acceptance, enclosing local milestone closeout |

### Export/import and return-value map

| Provider | Exports checked | Consumer and actual use |
| --- | --- | --- |
| Phase 1 records/store | `Action`, `Canary`, `Event`, `Store`, `StoreError` | Adapters construct Events with registered Canary IDs; Store inserts/reconstructs them; CLI catches StoreError and report reads fields (`store.py:110`, `sdk.py:162`, `network.py:167`, `monitors/inotify.py:342`, `report.py:30`). |
| Phase 1 creation | `SeedSpec`, `generate`, `GeneratedCanary`, `create_canary`, `seed` | `seed()` calls `generate()`, writes returned `.content`, then registers returned `.canary`; CLI and demo call the creation APIs (`generator.py:110`, `generator.py:158`, `generator.py:168`, `cli.py:192`, `demo.py:256`). |
| Phase 1 extensions | `EventSink`, `Monitor` | EventSink is injected into SDK, passive and HTTP adapters, with PolicySink invoking the downstream `record()` method. Monitor is documented for external lifecycle consumers; concrete monitors implement start/stop structurally. The audit exercised both protocols with real observations, described below. |
| Phase 2 matching | `TokenMatcher`, `MatchResult`, `PayloadTooLarge` | Observer calls `.match()` and consumes `.canaries`/`.bytes_scanned`; HTTPInspector calls `.match_encoded()`; bounded-input failures reach health recording and caller errors (`sdk.py:157`, `network.py:157`). |
| Phase 2 cooperative API | `Observer`, `ToolResult`, `ToolInvocationError` | Demo child calls read/copy/run_tool/observe_model and checks `ToolResult.returncode`; failure tests catch ToolInvocationError. The example also invokes a real tool and checks its return code (`demo.py:349`, `demo.py:354`, `demo.py:368`, `sdk.py:297`, `examples/observe_workspace.py:17`). |
| Phase 2 passive API | `InotifyMonitor`, `MonitorError` | CLI/demo construct, start, check and stop the monitor; CLI catches MonitorError. Actual kernel notifications call the sink (`cli.py:118`, `cli.py:132`, `cli.py:211`, `demo.py:197`, `monitors/inotify.py:373`). |
| Phase 3 inspection | `EncodedMatchResult`, `DecodeError`, `HTTPInspector` | Matcher returns encoded matches; inspector consumes canary/encoding fields and records or diagnoses them; Observer delegates HTTP/model/embedding inputs with `source="sdk"` (`matching.py:200`, `network.py:157`, `network.py:176`, `sdk.py:91`). |
| Phase 3 listener | `BlockingProxy`, `NetworkError` | CLI/demo start/check/stop the listener; accepted requests call HTTPInspector; failures propagate through check/stop and CLI catches NetworkError (`network.py:579`, `network.py:360`, `cli.py:228`, `demo.py:262`). |
| Phase 3 policy | `IgnoreRule`, `Policy`, `PolicySink`, `load_policy` | Explicit config is loaded before ordinary CLI state/artifact creation; ignore rules match Events; PolicySink annotates then persists every Event; reports inspect stored decisions (`cli.py:154`, `cli.py:181`, `policy.py:102`, `policy.py:128`, `report.py:23`). |

Class-name grep alone would incorrectly call `GeneratedCanary`, `MatchResult`, `EncodedMatchResult` and `ToolResult` orphaned. Their returned objects carry values consumed by subsequent phases. Conversely, no internal Monitor import/use is claimed: that protocol is an explicit external extension surface, not a hidden plugin registry or an implemented auditd/eBPF backend.

### Expected connection verdicts

All source references below are under `src/agentcanary/` unless stated otherwise.

| ID | Connection and end-to-end evidence | Verdict |
| --- | --- | --- |
| W01 | Templates → exclusive seeded files → `Store.register_many()` → registry/CREATE transaction consumed by later adapters (`templates.py:45`, `generator.py:110`, `generator.py:169`, `store.py:134`). | WIRED |
| W02 | Registry → Observer snapshot/refresh → exact matcher → supplied/completed-input Event with same canary ID (`sdk.py:82`, `sdk.py:86`, `sdk.py:157`, `sdk.py:168`). | WIRED |
| W03 | Registry path/digest/token → inotify validated inode snapshot → actual kernel READ with same ID and unknown PID (`monitors/inotify.py:192`, `monitors/inotify.py:234`, `monitors/inotify.py:342`). | WIRED |
| W04 | Phase 2 matcher → Phase 3 bounded representation traversal → HTTP match objects → structured Events (`matching.py:93`, `network.py:157`, `network.py:166`). | WIRED |
| W05 | Observer HTTP/model/embedding helpers → HTTPInspector using the same matcher, sink and run ID with SDK attribution (`sdk.py:91`, `sdk.py:103`, `network.py:259`). | WIRED |
| W06 | SDK read/copy/tool/model observations → injected/default sink → Store record transaction → query/report (`sdk.py:163`, `sdk.py:229`, `sdk.py:277`, `store.py:173`, `report.py:31`). | WIRED |
| W07 | Passive READ and coverage diagnostics → sink → durable Store → CLI report; worker failure reaches check/stop (`monitors/inotify.py:180`, `monitors/inotify.py:342`, `monitors/inotify.py:380`, `cli.py:163`). | WIRED |
| W08 | Actual loopback request → bounded parser → inspector → EXFILTRATION and recognized MODEL_REQUEST → sink/Store → fixed blocked response/report (`network.py:510`, `network.py:579`, `network.py:235`, `network.py:140`). | WIRED |
| W09 | Config → Policy/PolicySink → SDK, passive and HTTP records → retained decisions; no forwarding permission (`policy.py:132`, `policy.py:97`, `policy.py:128`, `sdk.py:75`, `cli.py:181`, `cli.py:185`). | WIRED |
| W10 | Store events + registry → type enrichment/redaction → text/JSON/JSONL, filters and presentation-only policy hiding (`store.py:198`, `cli.py:165`, `report.py:23`). | WIRED |
| W11 | Foundation + sensors → demo readiness → real child/tool/socket activity → ID/run/PID checks, byte/digest receipts, healthy cleanup → success export (`demo.py:254`, `demo.py:297`, `demo.py:300`, `demo.py:314`). | WIRED |
| W12 | Console/module CLI → `run_demo()` → same interpreter's installed `agentcanary.demo` child → Store/report; errors return nonzero (`cli.py:144`, `demo.py:183`, `demo.py:267`, `demo.py:391`, `__main__.py:1`). | WIRED |
| W13 | Public EventSink/Monitor/custom-template contracts → externally composed real observation → policy → common registry ID and report (`protocols.py:9`, `generator.py:83`, `docs/architecture.md:78`; independent extension check below). | WIRED |
| W14 | Package entry points/source inclusion → wheel/sdist → clean installed CLI/monitor/proxy/demo outside checkout → release evidence (`pyproject.toml:33`, `scripts/verify_install.py:71`, `scripts/verify_install.py:109`, `scripts/verify_install.py:128`). | WIRED |

## API Coverage

**Consumed: 10/10 recognized model paths. Orphaned: 0.** These are classifiers on the same local blocking endpoint, not separate provider implementations. Every path was exercised by this audit using a real `HTTPConnection("127.0.0.1", port)` and an issued custom marker; each produced a 403 plus retained EXFILTRATION and MODEL_REQUEST records with the registered ID. A percent-normalized/trailing-slash alias also passed.

| Route pair | Consumer evidence | Verdict |
| --- | --- | --- |
| `/chat/completions`, `/v1/chat/completions` | Audit loopback client; SDK call in `tests/test_http_inspection.py:83` also exercises the versioned route. | WIRED |
| `/completions`, `/v1/completions` | Audit loopback client → parser → `model_route()` → stored events/report. | WIRED |
| `/responses`, `/v1/responses` | Audit loopback client; demo's actual model request at `demo.py:374`; CLI request test at `tests/test_network.py:346`. | WIRED |
| `/messages`, `/v1/messages` | Audit loopback client; real versioned request at `tests/test_network.py:100`. | WIRED |
| `/embeddings`, `/v1/embeddings` | Audit loopback client; concurrent client at `tests/test_integration.py:50`. | WIRED |

The ordinary-path handler is also consumed: demo collector `/upload` and the audit's `/ordinary` request produce EXFILTRATION without invented model classification. An ordinary payload receives 403 with no matching canary event. All 13 audit HTTP requests returned 403. Source trace of `BlockingProxy` contains listener accept/read/respond operations and no upstream connect/DNS path; its real no-forwarding test is `tests/test_network.py:64`.

## Auth Protection and Local Trust Boundaries

**Session-authenticated sensitive areas: not applicable. Missing required auth connections: 0.** This release has no SaaS accounts, sessions or user-data API. Treating every listener route as missing authentication would contradict its specified local observation boundary.

Two required local boundaries are wired: Store uses private current-user directories/files checked at every connection (`filesystem.py:24`, `filesystem.py:52`, `store.py:50`), and BlockingProxy accepts only numeric loopback bind addresses (`network.py:311`). The latter is local accessibility, not client authentication. HTTP identity headers do not set PID/run: the inspector stores `pid=None` and its operator-configured run ID (`network.py:173`). Same-account tampering remains outside the protection claim.

## E2E Flows

**Complete: 13. Broken: 0.** “Complete” means the supported path, including its declared error/empty behavior, is connected. Independent execution in this pass and previously recorded release execution are distinguished below.

| Flow | Full path and error/empty outcome | Evidence |
| --- | --- | --- |
| F01 — Create/seed/custom | CLI/template → safe writes → atomic registry/CREATE → report. Existing files and ordinary write/Store failures preserve or roll back owned content; no cross-filesystem crash transaction is claimed. | `generator.py:78`; `tests/test_generator.py`; `tests/test_seed_rollback.py`; audit nine-artifact check. |
| F02 — Passive reads | Seeded digest/ID → validated inode watch → real file read → unknown-PID Event → Store/report. Missing/changed/duplicate/overflow coverage yields diagnostics and requires restart. | `monitors/inotify.py:221`, `:310`; audit nine watches and reads; `tests/test_monitor.py`; `tests/test_monitor_lifecycle.py`. |
| F03 — Cooperative propagation | SDK read → exclusive copy → real tool stdin/receipt → model/embedding inputs → caller-PID records → reports. Invocation evidence precedes spawn and remains an attempt on failure. | `sdk.py:178`, `:193`, `:251`; `demo.py:348`; independently executed installed-demo and attribution tests. |
| F04 — HTTP/model route | Real loopback client → bounded parser → recognized route/matcher → blocked-attempt records → response → report. Unknown markers produce no match, rather than a fabricated event. | `network.py:579`; independent all-route check and concurrent integration test. |
| F05 — Representations and diagnostics | HTTP/SDK fields → bounded plaintext/URL/JSON/base64/gzip processing → exact registered ID or explicit incomplete-coverage health/error → Store. Unsupported framing is rejected before a clean-scan claim. | `matching.py:93`; `network.py:72`, `:157`, `:510`; reviewed `test_http_inspection.py`, `test_network.py`, `test_inspection_boundaries.py`; release suite evidence. |
| F06 — Policy and presentation | Explicit TOML → strict policy → all adapters → retained annotations → optional hidden report rows. CREATE/health remain; invalid config fails before ordinary artifact creation; allowlisting still returns 403. | `cli.py:154`; `tests/test_policy.py:99`, `:128`, `:171`; two independently executed policy tests plus audit relay fixture. |
| F07 — CLI sensor lifecycle | Installed monitor/proxy command → start → flushed readiness → check loop → duration/signal shutdown → persisted evidence. Zero watches are disclosed; failed workers raise. | `cli.py:104`, `:221`; CLI lifecycle tests; installed verification at `scripts/verify_install.py:121`; release evidence. |
| F08 — Full installed demo | CLI → isolated seed → ready inotify/HTTP → installed child → copy/tool/mock model/HTTP → correlated chain and receipts → cleanup → reports and complete summary. | Independently executed `tests/test_demo.py:16`; `demo.py:242`; independent retained-demo check. |
| F09 — Failure and cleanup | Startup/coverage/sink/timeout/interruption/export failure → owned cleanup → nonzero/failed outcome. Summary completion is published only after successful export finalization. | Independently executed sink, missing-passive and export failure tests; `demo.py:59`, `:121`, `:316`; reviewed release/lifecycle regressions and recorded correction evidence. |
| F10 — Concurrency and correlation | Independent Store handles + concurrent SDK/HTTP/inotify → unique durable sequences → per-canary/run attribution → JSONL round-trip. Safe disappearing optional SQLite sidecars receive bounded revalidation. | Independently executed `tests/test_integration.py:13`; `store.py:50`, `:173`; `filesystem.py:52`; recorded concurrency/sidecar regressions. |
| F11 — Empty and snapshot refresh | Empty Store → valid empty report; empty monitor/proxy → health diagnostics. Registration after SDK snapshot remains undetected until explicit refresh, then matches. | Independent empty-registry fixture; executed `test_empty_reports_are_machine_readable` and `test_safe_origin_validation_and_snapshot_refresh`; `sdk.py:86`, `network.py:118`. |
| F12 — External adapters | Custom template → normal registry; custom EventSink relay composed with policy → all three sensor sources → Store/report. Structural Monitor consumer calls start/stop on a read adapter. | Independent extension fixture; `protocols.py`; `docs/architecture.md:78`. No future privileged backend is implied. |
| F13 — Install and use release | Built wheel/source archive → fresh environment/import check → help/create/seed/monitor/proxy/report/demo outside checkout → retained evidence. Docs/examples target these same callable APIs. | Independent archive metadata/current-source comparison; `scripts/verify_install.py:71`; reported six clean installations; docs/example call-site trace. |

## Detailed Findings

### Orphaned Exports

No unintended orphaned export. `Monitor` has no built-in class-name consumer because callers use concrete monitor APIs; it is an intentionally exported structural extension contract. The audit verified structural compatibility of InotifyMonitor, BlockingProxy and a disposable external read adapter, and actually called that adapter's lifecycle through to a stored SDK read. This is accounted for explicitly rather than reporting a nonexistent internal import.

### Missing Connections, Broken Flows and Unprotected Routes

None within the stated milestone scope. There are **0 BLOCKERs and 0 WARNINGs**. Earlier CR-01/02/03 findings remain resolved, with their original evidence and verification in `05-REVIEW.md`; they are not outstanding findings in this audit.

### Requirements Integration Map

Every status below is binary for product wiring. REL-03 additionally identifies the still-pending administrative completion clause.

| Requirement | Integration path | Status | Issue / boundary |
| --- | --- | --- | --- |
| CORE-01 | P1 eight built-ins → registry → P2 matcher/inotify and P3 HTTP → P1 typed report | WIRED | Audit read all eight built-ins plus custom through the common registry. |
| CORE-02 | P1 profiles/custom SeedSpec → safe generator → P2 observations → P5 documented example/package | WIRED | Trusted literal template input; no overwrite/no-follow and ordinary rollback contracts traced. |
| CORE-03 | P1 atomic registration/CREATE and Event model → P2/P3 writers → P4 concurrent chain → ordered reports | WIRED | Filesystem and database remain separate crash boundaries. |
| CORE-04 | P1 installed CLI/reports/protocols → P2/P3 commands/adapters → P4 demo → P5 installed verification | WIRED | Monitor is an intentional external structural contract, independently exercised. |
| OBS-01 | P1 registry/digest → P2 real inotify read and coverage health → P4 gate → report | WIRED | Passive PID remains unknown; readiness alone is not coverage. |
| OBS-02 | P1 token IDs → P2 read/copy/tool → P3 model/embedding inspection → P4 child receipts → report | WIRED | SDK PID identifies caller; supplied input is not semantic model/tool consumption. |
| OBS-03 | P1 concurrent Store → P2/P3 lifecycle/error paths → P4 cleanup → P5 sidecar/process corrections | WIRED | Custom sinks must return promptly; documented bounded shutdown and scheduling limits remain. |
| NET-01 | P4/CLI clients → P3 blocking listener/model classifier → P1 Store/report | WIRED | Ten model paths and ordinary path consumed; no upstream forwarding. |
| NET-02 | P1 issued tokens → P2 matcher → P3 bounded representations/framing diagnostics → Store/report | WIRED | Arbitrary transforms, encrypted/bypassing traffic and cross-field splits remain disclosed coverage gaps. |
| NET-03 | P3 strict policy → P2/P3 sinks → P1 safe Event fields/persistence → filtered reports | WIRED | Policy annotates retained evidence; it does not authenticate clients or allow forwarding. |
| E2E-01 | P1 creation → P2 real child read/copy/tool → P3 SDK model + real HTTP → P4 receipt/gate/export → P5 installed demo | WIRED | Full six-action chain and honest attribution independently verified. |
| E2E-02 | P1–3 failure/negative/concurrency contracts → P4 cross-sensor/failure tests → P5 correction regressions and release suites | WIRED | Focused paths rerun here; broader suite results are attributed release evidence. |
| REL-01 | P1 package configuration + P2/P3 sensors + P4 installed child → P5 quality/build/clean-install verifier | WIRED | Final artifacts match source. No hosted CI or local Python 3.13 execution is claimed. |
| REL-02 | P1–4 public APIs and limits → P5 README/docs/examples/license → distributed docs/examples and runnable entry points | WIRED | Source/docs/install interfaces agree; local publication only. |
| REL-03 | P1–4 reviewed implementation → P5 corrected defects → focused/full reruns → this audit → enclosing local archive | WIRED | Review/fix/rerun and audit handoff are connected. Archive/state evolution remains the parent's next administrative transaction, not an already completed fact. |

**Requirements with no cross-phase wiring:** None. All 15 touch a consumer, producer or verification boundary across phases. REL-03's final archive is administrative and is explicitly handed to the enclosing milestone finalizer.

## Verification Evidence and Limits

Independent execution during this audit:

1. A focused selection of **10 tests passed in 5.44s** on the default environment: concurrent sensors/report round-trip; installed CLI demo; demo HTTP sink failure; missing passive evidence; export failure; retained policy/report filtering; policy across real HTTP and passive reads; empty CLI reports; registry refresh; SDK HTTP/model/embedding attribution. These are the named cases in `tests/test_integration.py`, `test_demo.py`, `test_policy.py`, `test_cli.py` and `test_http_inspection.py` referenced above. No full suite was rerun.
2. A disposable synthetic fixture seeded all eight built-ins and a custom artifact, confirmed nine unique IDs/tokens and nine CREATE records, installed nine passive watches, and read all nine through the SDK. A custom EventSink relay composed with PolicySink received actual SDK/inotify/HTTP events and persisted them to Store. Copy, model and embedding calls retained the custom ID. Reports retained type/sequence/attribution, removed marker values, and hid policy rows without deleting stored events.
3. That fixture sent **13 real loopback requests**, all 403: ten recognized model paths, a normalized embedding alias, an ordinary matching path and an ordinary nonmatching control. It verified **23 HTTP canary records**, including **11 MODEL_REQUEST records**, common canary ID, operator run ID, unknown PID, blocking metadata and retained allowlist annotations. Empty reports and both adapters' empty-registry diagnostics also passed. All temporary fixture data was removed.
4. `scripts/verify_install.py`'s artifact inspection passed. Direct archive comparisons verified **all 17 Python modules in both wheel and sdist match current source byte-for-byte**. This audit read the clean-install verifier's actual subprocess calls and isolation checks; it did not repeat package installation or build dependency resolution.
5. The retained `agentcanary-demo-final` summary, Store and JSONL were independently checked: **12 records**, the complete six-action chain, `[403, 403]`, common canary/run labels, SDK child PID, unknown passive/HTTP PID and exported sequence agreement.

Reported evidence, read from `05-ACCEPTANCE.md` and the supplied release review, rather than rerun here: **220 tests without skips** on CPython 3.11.17, 3.12.3 and 3.14.8; Ruff lint/format for 87 files; strict mypy for 17 source modules; final wheel/sdist build; **six fresh clean installs** (wheel and source on each of those interpreters) with complete installed demos outside checkout. The independent correction reviewer ran ten demo publication/ownership regressions and 26 sidecar regressions. Hosted CI and Python 3.13 were not run locally.

The CLI and ordinary sensors preserve their documented observation boundaries: exact issued tokens and bounded representations; explicit registry refresh/restart; passive inode access with no actor attribution; SDK caller/input evidence; HTTP attempted transmission with no forwarding/client authentication; retained rather than deleted policy matches; and local evidence writable by the same account. No complete causal order, universal egress coverage, arbitrary-secret scrubbing, or hostile-process containment is inferred from the connected flows.

Only benign synthetic local fixtures, local subprocesses and literal loopback application connections were used. No source changes, commits, external probes or external ship actions were performed. The parent may proceed to the local milestone audit/archive/state transaction.
