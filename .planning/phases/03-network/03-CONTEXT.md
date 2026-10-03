# Phase 3: HTTP and model request inspection - Context

Gathered: 2026-10-03
Status: Ready for planning after phase 2 verification

## Phase Boundary
Local HTTP interception, model/API input observation, bounded common-representation detection, destination privacy, and explicit allowlist/ignore policy. No forwarding or remote dependencies.

## Implementation Decisions
- Add a loopback-only HTTP inspection endpoint, usable as an explicit HTTP proxy or direct mock API endpoint. It ALWAYS blocks and NEVER resolves/connects to the supplied upstream destination, regardless of policy. Numeric loopback binds only; port 0 for tests. Provide CLI serve/proxy command with readiness, finite duration and graceful termination.
- Inspect request target, headers and complete bounded body for exact issued markers. Emit EXFILTRATION only on token sightings, plus MODEL_REQUEST for recognized model routes (chat/completions, responses, messages, embeddings). Classification means endpoint/input observation, not a real provider request or delivered exfiltration.
- HTTP events have unknown client PID. Listener/run correlation is operator-controlled; ignore spoofed PID/run headers as identity. Never log raw headers, body, arguments, errors containing input, URL userinfo/query/fragment, or arbitrary URL paths. Retain sanitized origin and recognized model route only.
- SDK helpers inspect explicit HTTP/model input before TLS without sending traffic. Preserve source=SDK with caller PID and clear input-observed provenance. Add model and embedding examples in tests.
- Support plaintext, percent-encoding, JSON unicode/string escaping, base64 standard/url-safe (whole payload or common encoded fields), and gzip HTTP content encoding with strict expansion limits. Match known full marker substrings; unknown markers do not trigger. Bound total decode work, candidate count, recursion and bytes, with diagnostics when incomplete. Do not promise arbitrary transformations.
- Bounded concurrent clients, read deadlines, request/header/body limits. Reject unsupported or ambiguous framing (e.g. duplicate Content-Length, unsupported Transfer-Encoding, CONNECT TLS tunnels) with explicit health evidence and deterministic responses. Chunked support is optional if rejected clearly; truncated/gzip errors must never count as a complete clean scan. No raw default http.server request logging or reflected error pages.
- Strict explicit TOML configuration (stdlib tomllib) with typo/type validation. Exact destination origins for allowlists; ignore by source/action/canary ID and optionally path. Preserve audit evidence: annotate policy matches in metadata instead of deleting CREATE or observations. Reports show decision and can optionally hide ignored/allowlisted entries. Policy never enables forwarding. Integrate consistently across SDK, filesystem and HTTP via EventSink wrapper where practical.
- Maintain stdlib-only runtime unless a concrete need justifies dependency. Core SQLite/SDK APIs are established; preserve target CLI commands and report format conventions.

## Existing Code Insights
Observer.observe(Action,payload,destination,metadata,provenance) accepts bytes/text, attaches caller PID and stores only evidence. TokenMatcher owns a registry snapshot, refresh is explicit. InotifyMonitor and SDK take EventSink implementations. Event metadata permits only reviewed scalar keys. Add policy/encoding fields intentionally. docs/threat-model.md defines evidence boundaries.

## Deferred Ideas
Transparent TLS interception, arbitrary TCP/DNS/QUIC inspection, upstream forwarding and privileged enforcement are out of scope. Demo and final package/docs are phases 4/5.
