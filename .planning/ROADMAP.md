# Roadmap: AgentCanary

## Milestone v0.1 — Local release

A traceable synthetic canary lifecycle, with explicit observation boundaries and reproducible local verification.

## Phases

- [x] **Phase 1: Foundation and safe canary lifecycle** — Create, seed and report synthetic canaries safely using a durable extensible event model.
- [ ] **Phase 2: Filesystem and attributed observations** — Observe file access and explicitly attributed read/copy/tool interactions with honest source evidence.
- [ ] **Phase 3: HTTP and model request inspection** — Detect token propagation through HTTP and model requests with bounded parsing and local-only interception.
- [ ] **Phase 4: End-to-end demo and adversarial integration** — Prove the complete canary chain with a real subprocess and loopback HTTP and exercise failure boundaries.
- [ ] **Phase 5: Release hardening and documentation** — Verify installation, audit the implementation, fix weaknesses and document a polished local release.

### Phase 1: Foundation and safe canary lifecycle

**Goal:** Create, seed and report synthetic canaries safely using a durable extensible event model.
**Depends on:** Nothing
**Requirements:** CORE-01, CORE-02, CORE-03, CORE-04
**Success Criteria:**
1. Generate uniquely identified, unmistakably synthetic, nonfunctional AWS, OpenAI, Anthropic, kubeconfig, SSH, env, database, and payroll canaries.
2. Seed realistic profiles and safe custom text templates without overwriting files or following symlinks.
3. Persist creation and structured events atomically with timestamps, identifiers, action, source, optional process and destination.
4. Provide installable Python package, useful CLI help, create/seed/report, text/JSON/JSONL reports, and extension contracts.

**Plans:** 1/1 plans executed
- [x] 01-01-PLAN.md — Foundation and safe canary lifecycle

### Phase 2: Filesystem and attributed observations

**Goal:** Observe file access and explicitly attributed read/copy/tool interactions with honest source evidence.
**Depends on:** Phase 1
**Requirements:** OBS-01, OBS-02, OBS-03
**Success Criteria:**
1. Detect real Linux file reads without privileges; report health and missing watches; never fabricate process attribution.
2. Provide cooperative SDK observations for read, copy, tool input and embedding/model input with PID and run correlation.
3. Keep monitoring and event recording safe under concurrent processes, file replacement, failures and shutdown.

**Plans:** 1 plan
- [ ] 02-01-PLAN.md — Filesystem and attributed observations

### Phase 3: HTTP and model request inspection

**Goal:** Detect token propagation through HTTP and model requests with bounded parsing and local-only interception.
**Depends on:** Phase 2
**Requirements:** NET-01, NET-02, NET-03
**Success Criteria:**
1. Inspect real HTTP requests locally and record attempted exfiltration without forwarding; identify model API paths.
2. Detect exact issued tokens in plaintext, common URL/JSON/base64 representations and bounded gzip bodies; reject unsupported framing explicitly.
3. Provide strict local allowlist/ignore configuration, provenance, safe metadata and no body/credential logging.

**Plans:** 1 plan
- [ ] 03-01-PLAN.md — HTTP and model request inspection

### Phase 4: End-to-end demo and adversarial integration

**Goal:** Prove the complete canary chain with a real subprocess and loopback HTTP and exercise failure boundaries.
**Depends on:** Phase 3
**Requirements:** E2E-01, E2E-02
**Success Criteria:**
1. Demonstrate creation → read → copy/tool → mock model request → attempted HTTP exfiltration using a simulated agent and loopback only.
2. Test major failure paths, false positives/negatives, concurrency, attribution and network blind spots.

**Plans:** 1 plan
- [ ] 04-01-PLAN.md — End-to-end demo and adversarial integration

### Phase 5: Release hardening and documentation

**Goal:** Verify installation, audit the implementation, fix weaknesses and document a polished local release.
**Depends on:** Phase 4
**Requirements:** REL-01, REL-02, REL-03
**Success Criteria:**
1. Pass automated tests, lint, strict type checks, wheel/sdist build and clean-environment installation.
2. Publish local professional README, architecture, threat model, limitations, examples, contribution and security guidance, and license.
3. Complete autonomous architectural/security review, fix findings, rerun relevant checks, archive GSD milestone locally.

**Plans:** 1 plan
- [ ] 05-01-PLAN.md — Release hardening and documentation

## Progress

| Phase | Plans Complete | Status | Completed |
|---|---|---|---|
| 1. Foundation and safe canary lifecycle | 1/1 | Complete | 2026-10-03 |
| 2. Filesystem and attributed observations | 0/1 | Not started | - |
| 3. HTTP and model request inspection | 0/1 | Not started | - |
| 4. End-to-end demo and adversarial integration | 0/1 | Not started | - |
| 5. Release hardening and documentation | 0/1 | Not started | - |
