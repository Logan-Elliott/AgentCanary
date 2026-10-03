# Requirements: AgentCanary

Defined: 2026-10-03

## v0.1 Requirements

### Foundation and safe canary lifecycle

- [x] **CORE-01**: Generate uniquely identified, unmistakably synthetic, nonfunctional AWS, OpenAI, Anthropic, kubeconfig, SSH, env, database, and payroll canaries.
- [x] **CORE-02**: Seed realistic profiles and safe custom text templates without overwriting files or following symlinks.
- [x] **CORE-03**: Persist creation and structured events atomically with timestamps, identifiers, action, source, optional process and destination.
- [x] **CORE-04**: Provide installable Python package, useful CLI help, create/seed/report, text/JSON/JSONL reports, and extension contracts.

### Filesystem and attributed observations

- [ ] **OBS-01**: Detect real Linux file reads without privileges; report health and missing watches; never fabricate process attribution.
- [ ] **OBS-02**: Provide cooperative SDK observations for read, copy, tool input and embedding/model input with PID and run correlation.
- [ ] **OBS-03**: Keep monitoring and event recording safe under concurrent processes, file replacement, failures and shutdown.

### HTTP and model request inspection

- [ ] **NET-01**: Inspect real HTTP requests locally and record attempted exfiltration without forwarding; identify model API paths.
- [ ] **NET-02**: Detect exact issued tokens in plaintext, common URL/JSON/base64 representations and bounded gzip bodies; reject unsupported framing explicitly.
- [ ] **NET-03**: Provide strict local allowlist/ignore configuration, provenance, safe metadata and no body/credential logging.

### End-to-end demo and adversarial integration

- [ ] **E2E-01**: Demonstrate creation → read → copy/tool → mock model request → attempted HTTP exfiltration using a simulated agent and loopback only.
- [ ] **E2E-02**: Test major failure paths, false positives/negatives, concurrency, attribution and network blind spots.

### Release hardening and documentation

- [ ] **REL-01**: Pass automated tests, lint, strict type checks, wheel/sdist build and clean-environment installation.
- [ ] **REL-02**: Publish local professional README, architecture, threat model, limitations, examples, contribution and security guidance, and license.
- [ ] **REL-03**: Complete autonomous architectural/security review, fix findings, rerun relevant checks, archive GSD milestone locally.

## Future requirements

- Optional auditd/eBPF monitors and independently protected remote sinks.
- Opt-in TLS interception with explicit trust lifecycle; never imply passive encrypted-payload coverage.

## Traceability

| Requirement | Phase | Status |
|---|---|---|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 1 | Complete |
| OBS-01 | Phase 2 | Pending |
| OBS-02 | Phase 2 | Pending |
| OBS-03 | Phase 2 | Pending |
| NET-01 | Phase 3 | Pending |
| NET-02 | Phase 3 | Pending |
| NET-03 | Phase 3 | Pending |
| E2E-01 | Phase 4 | Pending |
| E2E-02 | Phase 4 | Pending |
| REL-01 | Phase 5 | Pending |
| REL-02 | Phase 5 | Pending |
| REL-03 | Phase 5 | Pending |

All 16 requirements mapped. No remote publication is authorized.
