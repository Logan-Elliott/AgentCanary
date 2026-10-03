---
phase: 03-network
plan: 01
subsystem: network
tags: [http, loopback, sdk, bounded-decoding, toml, policy]
requires:
  - phase: 02-observations
    provides: Registry snapshots, cooperative Observer, EventSink and Linux monitoring
provides:
  - Bounded loopback blocking HTTP endpoint with explicit failures and no upstream I/O
  - Common representation matching and cooperative pre-TLS HTTP/model/embedding inspection
  - Strict retained-audit policy, CLI configuration and optional report filtering
affects: [04-integration, 05-release]
tech-stack:
  added: []
  patterns: [bounded-socket-workers, absolute-read-deadline, exact-origins, retained-policy-annotations]
key-files:
  created: [src/agentcanary/network.py, src/agentcanary/policy.py, tests/test_http_inspection.py, tests/test_network.py, tests/test_policy.py]
  modified: [src/agentcanary/matching.py, src/agentcanary/sdk.py, src/agentcanary/models.py, src/agentcanary/report.py, src/agentcanary/cli.py, src/agentcanary/__init__.py]
key-decisions:
  - "Every listener request is blocked without upstream DNS or connections, including allowlisted requests. HTTP PID remains unknown."
  - "Policy keeps audit events and annotates exact-origin or conjunctive ignore matches; CREATE and health are unaffected."
  - "Decoding is bounded by input bytes, cumulative work, candidate count and depth; incomplete scans produce health evidence."
  - "Tool argv is snapshotted once before validation, observation and execution so sink callbacks cannot change the observed invocation."
requirements-completed: [NET-01, NET-02, NET-03]
coverage:
  - id: D1
    description: Real HTTP requests are blocked with no upstream resolution or connection and honest provenance
    requirement: NET-01
    verification:
      - kind: integration
        ref: tests/test_network.py
        status: pass
    human_judgment: false
  - id: D2
    description: Registered markers survive common bounded representations; invalid framing and exhausted budgets are explicit
    requirement: NET-02
    verification:
      - kind: integration
        ref: tests/test_http_inspection.py and tests/test_network.py
        status: pass
    human_judgment: false
  - id: D3
    description: Strict configuration annotates retained evidence consistently without persisting request content
    requirement: NET-03
    verification:
      - kind: integration
        ref: tests/test_policy.py
        status: pass
    human_judgment: false
actuals:
  tokens: 21238
  tasks: 3
  commits: 5
commits: 5
plan_head_before: b65c1841fd6d34fa6890f39864724ecbda4b371a
plan_head_after: 40ab6de3bd50524e0e9760112c1c979767063555
duration: 23min
completed: 2026-10-03
status: complete
---

# Phase 3 Plan 1: HTTP and model request inspection Summary

**A bounded loopback HTTP endpoint blocks every attempt, records exact issued markers across common encodings, and retains origin/ignore policy decisions without request-content logging.**

## Accomplishments

- Added complete-field inspection for targets, headers and bodies, with plaintext, percent escapes, JSON string/key escapes, standard or URL-safe base64, common form fields and bounded gzip. Matching deduplicates each canary/action per observation. Full issued markers embedded beside other text match; unknown, partial, mutated and cross-field split markers do not.
- Added HTTP/1 loopback endpoint with port 0, bounded concurrent workers, absolute request deadline, request/header/body bounds, bounded gzip expansion, deterministic static response bodies and explicit health failures. Chunked/other transfer encoding, CONNECT, Expect, ambiguous lengths/hosts, truncated input and malformed framing are rejected. No upstream connection or DNS lookup exists.
- Added SDK pre-TLS HTTP, model and embedding helpers that preserve caller PID/run correlation and never send traffic. Listener events retain `pid=None`; client identity headers are ignored.
- Added strict TOML configuration and composable policy sink. Exact origin allowlisting and conjunctive source/action/canary-ID ignore rules annotate retained evidence. CREATE and health events remain unchanged; optional report filtering changes presentation only. Allowlisting never changes blocking behavior.
- Added CLI `proxy` / `serve` readiness, duration, SIGTERM and Ctrl-C handling; SDK/monitor/proxy policy composition; report policy display and `--hide-policy`.

## Task Commits

1. Bounded representations and inspection API — `dc59ec9`.
2. Local blocking HTTP endpoint and CLI — `4a75563`.
3. Strict retained policy and failure coverage — `40ab6de`.

The measured Git span contains **5 commits**, including root-agent commits `308b096` (monitor review corrections) and `95982d6` (architecture/limitations documentation). The task list contains this executor's three commits. Actual tokens use chars/4 over the realized diff in this phase's eleven source/test files. All commits use Logan-Elliott <dev.loganelliott@gmail.com>.

## Demo Integration APIs

All following types are top-level `agentcanary` exports; existing APIs remain compatible.

```python
BlockingProxy(store: Store, *, host: str = "127.0.0.1", port: int = 0,
              sink: EventSink | None = None, run_id: str | None = None,
              max_body_bytes: int = 1048576, max_header_bytes: int = 32768,
              max_workers: int = 8, read_timeout: float = 5.0)
# .start(), .stop(), .check(); context-manager support
# .url (http://127.0.0.1:PORT or IPv6 equivalent), .host, .port, .run_id
# .ready: threading.Event, .running: bool, .error: str | None
# .inspector.refresh() explicitly replaces the live registry snapshot.
# .check()/stop() raise NetworkError for worker/sink failures.

HTTPInspector(store: Store, *, sink=None, run_id=None, max_bytes=1048576,
              source="http", matcher=None)
HTTPInspector.inspect(method, target, *, headers=(), body=b"", blocked=False)
HTTPInspector.inspect_model(payload, *, destination, embedding=False)
# Both return tuple[Event, ...]; no network I/O. source is http or sdk.
# .refresh(), .registry_count; headers accepts a mapping or sequence of pairs.

Observer(store, *, run_id=None, sink=None, max_bytes=1048576, policy=None)
Observer.observe_http(method, url, *, headers=(), body=b"") -> tuple[Event, ...]
Observer.observe_model(payload, *, destination) -> tuple[Event, ...]
Observer.observe_embedding(payload, *, destination) -> tuple[Event, ...]

TokenMatcher.match_encoded(parts, *, max_candidates=256, max_depth=4,
                           max_work_bytes=None) -> EncodedMatchResult
# parts: Sequence[bytes | str]; total input <= max_bytes.
# Default cumulative candidate bytes <= 8*max_bytes, <=256 JSON nodes/candidates.
# .matches contains .canary and .encoding; .bytes_scanned is cumulative scan work.
# PayloadTooLarge and DecodeError indicate incomplete coverage.

Policy(allow_origins=frozenset(), ignore=())
IgnoreRule(source=None, action=None, canary_id=None)
PolicySink(sink: EventSink, policy: Policy)
load_policy(path: str | Path) -> Policy
render_report(events, *, format="text", canaries=(), hide_policy=False)
```

For the demo, construct the Store and canaries first, then use `with BlockingProxy(store, run_id=run_id) as proxy:`. Send a real `http.client.HTTPConnection(proxy.host, proxy.port)` request with an absolute synthetic destination such as `https://model.invalid/v1/responses` or a direct `/v1/responses` target. Read the response body and close the client. Successful inspection returns **403**, including requests with no matching marker. `.check()` verifies no sink/worker failure occurred. Proxy port 0 is available before `start()` returns.

Matching recognized `/v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/messages`, `/v1/embeddings` (or their unversioned forms, with percent-normalized path and optional trailing slash) emits both EXFILTRATION and MODEL_REQUEST. Other paths emit only EXFILTRATION. A body-supplied model name is never retained. SDK model/embedding helpers emit MODEL_REQUEST only; their provenance describes supplied input and does not imply delivery.

Listener events use `source="http"`, `provenance="http_request_blocked"`, `operation="transmission_attempt"`, `blocked=True` and `attribution="unknown_client"`. SDK HTTP events use `source="sdk"`, `provenance="sdk_http_input"`, `blocked=False` and actual caller PID. SDK model/embedding provenance is `sdk_model_input`; operation distinguishes `model_input` and `embedding_input`. The destination contains a canonical HTTP(S) origin, without userinfo, path, query or fragment. Only recognized routes appear in route metadata.

## Configuration Contract

```toml
version = 1
allow_origins = ["https://model.invalid"]

[[ignore]]
source = "sdk"
action = "READ"
# canary_id = "canonical-canary-uuid"  # optional; all supplied selectors must match
```

Configuration is loaded only from an explicit path; regular files, no-follow directory access, 64 KiB input limit, maximum 256 origins and 256 rules. Unknown fields and invalid types/versions/actions/UUIDs fail before CLI artifact creation. Origins cannot contain credentials, paths beyond a trailing slash, queries, fragments or wildcards. Scheme/host/default port are canonicalized, and matching uses exact canonical origins.

`Observer(..., policy=load_policy(path))` applies configuration directly. `sink=PolicySink(store, policy)` composes with HTTPInspector, BlockingProxy and InotifyMonitor. CLI uses `agentcanary --state-dir state --config policy.toml proxy --port 0 --duration 30`; monitor uses the same global config option. `report --hide-policy` hides only stored `ignored`/`allowlisted` observations; policy is not retrospectively applied to old events. Ignore has precedence over allowlist. The default observation decision is `observed`; matched ignore rules include their 1-based `policy_rule` index.

## Verification

- `uv run pytest -q tests`: **159 passed**, no skips, 39.16 seconds.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed, 63 files at verification time.
- `uv run mypy src`: passed, 16 source files, strict mode.
- Real socket/HTTP clients exercise IPv4/IPv6, forbidden upstream resolution/connect, concurrent requests, worker saturation, absolute trickle deadlines, incomplete/framing failures, body/header/gzip limits, privacy and source attribution.
- Real CLI processes exercise readiness, port 0, finite duration, SIGTERM and Ctrl-C. Injected startup/sink failures release sockets/workers and expose sanitized errors. Policy integration covers SDK, actual HTTP, passive filesystem reads and reports.
- Regression `tests/test_policy.py::test_argument_snapshot_matches_actual_invocation_after_sink_mutation` proves the exact argv inspected is executed despite mutation by a recording callback.

## Deviations from Plan

**[Rule 1 - Bug / parent-requested review correction] Snapshot tool argv before observation.** The parallel Phase 2 review found that caller-owned argv could change in a sink callback between matching and subprocess execution. `Observer.run_tool` now snapshots once and uses that snapshot for validation, scanning and spawning. Fixed in `40ab6de`; the regression above passes. This closes the outstanding SDK review finding.

The planned listener uses a small bounded socket parser rather than `http.server`; research allowed this choice. The restricted HTTP/1 subset makes header/body/deadline bounds explicit and avoids default request/error logging. Initial socket tests also clarified that a saturated listener may close before the client half-closes; tests now consume the complete framed response instead of requiring an additional EOF from an already rejected connection.

GSD state, metrics, session, roadmap and requirements handlers ran. The handlers retained the previous phase pointer and In Progress roadmap status despite verified completion; counters, Phase 3 status and the generated state.json were normalized to 3/5 complete while preserving later phases as pending.

## Boundaries and Residual Limits

- This endpoint is an explicit local observation boundary, not machine-wide egress enforcement. It cannot inspect encrypted tunnels, direct external sockets, QUIC or requests bypassing it. CONNECT/chunked are rejected explicitly; there is no TLS listener or HTTP/2 support.
- One request is handled per connection. No keepalive or pipelining is supported. A complete request is required for matching; rejected/unsupported/truncated requests produce health diagnostics and are not treated as clean scans.
- Decoding covers bounded common representations, not encryption, hashing, arbitrary transforms, marker mutation or splitting across fields/operations. Diagnostic errors may accompany conservative rejection of malformed JSON-like representations.
- Registry refresh is explicit. Empty snapshots produce a startup diagnostic. Ready means the listener is available, not that a canary exists or every possible representation is supported.
- A hostile or indefinitely blocking custom sink cannot be safely killed as a Python thread. stop() bounds joins to two seconds and raises `NetworkError` if cleanup cannot finish; ordinary built-in and injected failing sinks are verified.
- Separate EXFILTRATION/MODEL_REQUEST records use individual sink calls. A sink failure can retain a prefix of a request's events; check()/stop() surfaces the failure rather than claiming complete evidence.

## Threat Flags

| Flag | File | Description |
| --- | --- | --- |
| threat_flag: network_endpoint | src/agentcanary/network.py | Planned local socket boundary: numeric loopback only, bounded input/workers, fixed error bodies and no forwarding path; reviewed against docs/threat-model.md. |
| threat_flag: config_file_access | src/agentcanary/policy.py | Explicit bounded regular TOML file read through no-follow directory access; strict schema, retained audit and no forwarding semantics. |

## Known Stubs

None. No skipped tests, unrun verification commands, authentication gates or external setup remain.

## Next Phase Readiness

Phase 4 can compose creation, passive reads, SDK copy/tool/model and real local HTTP using the API contract above. No external credentials, providers, package installation or deployment are required.

## Self-Check: PASSED

All five newly created source/test files and both phase documents exist. All three task hashes resolve to Git commits. The final regression and quality checks above passed without skipped tests.
