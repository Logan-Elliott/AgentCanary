---
phase: 03-network
reviewed: 2026-10-03T23:09:28Z
depth: deep
files_reviewed: 12
files_reviewed_list:
  - src/agentcanary/matching.py
  - src/agentcanary/network.py
  - src/agentcanary/policy.py
  - src/agentcanary/sdk.py
  - src/agentcanary/cli.py
  - src/agentcanary/report.py
  - src/agentcanary/models.py
  - src/agentcanary/__init__.py
  - tests/test_http_inspection.py
  - tests/test_network.py
  - tests/test_policy.py
  - tests/test_inspection_boundaries.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
historical_findings:
  critical: 2
  warning: 0
  info: 0
  total: 2
status: clean
resolution_status: resolved
reviewed_implementation: 40ab6de3bd50524e0e9760112c1c979767063555
fixes_verified_through: f34edfc30512af40c513f74d43b32d10434fd74c
fixes_verified: 2026-10-03T23:12:40Z
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-03T23:09:28Z  
**Depth:** deep  
**Files reviewed:** 12, including the focused correction test file  
**Status:** resolved — no outstanding findings; canonical workflow status `clean`  
**Corrections verified:** 2026-10-03T23:12:40Z

## Summary

Two historical BLOCKER findings affected the claimed inspection and policy boundaries. Origin display redaction could change the identity used for exact allowlist decisions. Default JSON parsing could discard repeated members before their string representations were examined, while still returning a completed scan. Both are resolved by `f34edfc`, with the correction source inspected and all six dedicated regressions passing independently. Original severities and evidence remain below; frontmatter `findings` counts outstanding issues and `historical_findings` preserves the original totals. Neither finding involved a forwarding path or a claim of upstream delivery.

The original review used committed Phase 3 source through `40ab6de`, with the completed phase summary at `cbcee77` as context. Final verification inspected only the focused source corrections and boundary tests in `f34edfc`. Ongoing demo work was excluded. All scoped source and tests were read, including the existing observation contracts on which SDK and network extensions depend. No structural pre-pass or external reviewer evidence was supplied.

## Narrative Findings (AI reviewer)

### CR-01: Display redaction changes the identity used for exact-origin policy

**Classification:** BLOCKER  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/network.py:32-54`; `/home/gsd/projects/agent-canary/src/agentcanary/policy.py:22-41` and `105-110` at `40ab6de`  
**Disposition:** Resolved by `f34edfc`; adapter metadata, policy/configuration validation and focused regressions were independently verified.

**Issue:** `safe_origin()` replaces a synthetic-marker hostname component with the common display label `redacted`, then returns that result as the event destination. `Policy.annotate()` performs its exact allowlist comparison using this already-redacted destination. Policy configuration also canonicalizes allowed origins through the same redaction function. Consequently distinct origins can collapse to one comparison key, and an allowlisted decision can describe an origin different from the actual supplied origin. `report --hide-policy` can then hide that incorrectly classified observation. The retained database still contains the event, and the listener still blocks the request; this finding does not claim an egress-enforcement failure.

**Evidence:** The source applies a many-to-one hostname substitution at `network.py:42` before the returned canonical origin is used by `policy.py:108`. No independent unredacted comparison identity or redaction flag reaches the policy layer in the reviewed implementation. The existing origin tests cover suffix, scheme, port and userinfo differences, but do not cover this interaction between privacy redaction and policy equality. No allowlist-bypass request or external probe was performed.

**Fix:** Keep policy identity separate from display redaction, or conservatively prohibit allowlist matches for events whose origin required redaction. Carry a reviewed boolean indication of that condition through the HTTP/model adapters and require it to be false before matching an allowlist. Reject synthetic-marker-containing allowlist entries instead of silently converting them into a different origin. Preserve token-free event destinations and the always-block listener behavior. Add focused tests for redaction metadata, ordinary exact-origin matches, policy decisions on flagged events and strict configuration rejection.

**Verified correction:** `_origin_details()` now returns both the token-free display origin and a boolean indicating hostname redaction. HTTP and model/embedding inspection carries that value in reviewed `destination_redacted` metadata. Policy refuses allowlist classification when the value is true, while ordinary preserved-identity matches continue to work. Allowlist configuration rejects marker-bearing hostnames instead of changing their identity. Dedicated tests cover both boolean policy cases, adapter propagation, token-free evidence and configuration rejection.

### CR-02: Repeated JSON members disappear before representation inspection

**Classification:** BLOCKER  
**File:** `/home/gsd/projects/agent-canary/src/agentcanary/matching.py:145-169` at `40ab6de`; incomplete-scan handling `/home/gsd/projects/agent-canary/src/agentcanary/network.py:149-155`  
**Disposition:** Resolved by `f34edfc`; duplicate-name rejection and health propagation regressions passed independently.

**Issue:** `match_encoded()` calls `json.loads()` with its default object construction and then walks the resulting dictionary's keys and values. Repeated member names are collapsed before that walk, retaining only the last value. An earlier escaped or encoded string value is therefore unavailable to the representation scanner. The input can return a successful completed result instead of the `DecodeError`/health evidence required for incomplete inspection. Matching the raw JSON bytes first does not recover a marker that required decoding from the discarded string value.

**Evidence:** Source inspection establishes the lossy conversion at `matching.py:147` and the subsequent walk of only surviving dictionary contents at `163-169`. A benign check containing two ordinary, nonsecret string values under the same member name returned a completed empty match result against committed `40ab6de`. No marker-evasion payload, listener bypass or exploitation sequence was constructed.

**Fix:** Reject repeated JSON member names explicitly using an object-pairs hook and a bounded reason such as `DecodeError("duplicate_json_key")`, allowing existing inspector error handling to persist an incomplete-coverage diagnostic. Alternatively preserve every object pair and inspect all values within the existing node/candidate/work budgets. Cover top-level and nested duplicates with ordinary values, verify the inspector emits the bounded health reason, and retain positive tests for unique-member JSON.

**Verified correction:** JSON object construction uses `_unique_object`, which rejects repeated names before dictionary conversion can discard their values. The distinct `DecodeError("duplicate_json_key")` passes through the parser unchanged to the inspector's health-recording path. Tests cover top-level and nested duplicate names with ordinary values, assert the durable diagnostic, and confirm the same member name in separate objects remains valid.

## Review evidence and boundaries

For final correction verification, the reviewer read the relevant `f34edfc` diff and independently ran `tests/test_inspection_boundaries.py` against that commit's modules: **6 passed**. The parent reported **48 focused HTTP/policy/boundary tests passed**, scoped lint/format checks and strict mypy. This was a narrow correction check; whole-project review and final release verification remain separate work.

Cross-file tracing covered:

- Socket framing and deadline enforcement through bounded body/gzip handling, HTTP field inspection, representation matching and immutable event construction.
- SDK HTTP/model/embedding inputs through their shared registry snapshot, caller-PID provenance, origin sanitization, policy composition and event sinks.
- Strict policy-file reading and validation through retained annotations and presentation-only report filtering.
- Listener startup, request workers, semaphore ownership, socket closure, saturation, sink failure, check/stop, restart and CLI signal handling.

The review considered complete-field matching, deduplication, independent field boundaries, decode-depth/candidate/work limits, invalid JSON/gzip diagnostics, ambiguous HTTP headers, body/header bounds, static responses, snapshot refresh and protected CREATE/health records. No additional material finding was identified in this committed scope. This statement is limited to the inspected implementation and exercised checks, rather than a guarantee of universal parsing coverage or thread scheduling behavior.

Before this review, the remaining Phase 2 argv correction was independently inspected in `40ab6de`. The exact requested regression, `tests/test_policy.py::test_argument_snapshot_matches_actual_invocation_after_sink_mutation`, passed against committed modules: **1 passed**. Phase 2's review now records all four historical findings as resolved. This verification also covers the argv change included in Phase 3.

Committed modules were loaded from Git objects in memory so concurrent working-tree changes could not affect the targeted checks. Only benign synthetic/local checks were used. No whole-suite rerun, source/test edit or commit was performed by this reviewer. The executor's reported 159-test result is contextual evidence and is not represented as an independent reviewer run.

The following are declared scope limits, not additional findings:

- The listener binds a numeric loopback address and has no upstream connection or DNS path. It is an explicit observation endpoint, not machine-wide network enforcement or a transparent TLS proxy.
- Listener PID remains unknown; SDK PID identifies the calling process. Client identity headers do not establish process identity. EXFILTRATION denotes an observed attempt, while SDK helpers describe supplied input.
- Only one bounded HTTP/1 request is handled per connection. CONNECT, transfer encoding, Expect, malformed framing and incomplete inputs are explicitly rejected. Keepalive, pipelining, TLS interception and HTTP/2 are outside the supported subset.
- Supported decoding is bounded and representation-specific. Encryption, arbitrary transformations, marker mutation and splitting across independent fields or operations remain outside detection. Conservative errors on malformed JSON-like candidates are already disclosed; CR-02 instead concerns a lossy scan that currently returns success.
- Request bodies, authorization values, raw argument arrays and model names are not persisted by the adapters. Origin display data is intentionally retained; CR-01 concerns the subsequent use of a redacted display value for policy identity.
- Policy annotations retain audit records and never permit forwarding. `--hide-policy` affects presentation only. Separate sink calls can retain a prefix of a request's events if a later sink operation fails, and the failure is surfaced.
- Custom sinks may block indefinitely; bounded shutdown reports failure when workers cannot finish. Linux with the documented filesystem/proc requirements remains the supported platform through the underlying Store.

---

_Reviewer: foundation_review_astra (gsd-code-reviewer)_  
_Depth: deep_
