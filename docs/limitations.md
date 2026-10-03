# Limitations

The security invariant is conditional on the configured observation boundaries: a registered marker can be correlated from creation through observed access and propagation to an observed transmission attempt. No event does not mean no interaction occurred.

| Area | Coverage and limitation |
| --- | --- |
| Platform | Linux, Python 3.11+, and mounted `/proc`; no root or kernel instrumentation required |
| Filesystem reads | Registered, validated inode snapshot only; unknown actor PID; notifications may coalesce |
| Copied files | Explicit SDK copy and subsequent marker sightings; passive scanning does not discover all copies |
| New/changed artifacts | Explicit SDK refresh or monitor restart; modified files fail digest validation |
| Snapshot timing | Startup, validation, shutdown, replacement and overflow create observation gaps |
| Special access | mmap, alternate filesystems/access paths, and unobserved namespaces may evade inotify |
| Tool attribution | SDK caller and supplied invocation input; not proof of child consumption or meaning |
| HTTP interception | Only requests reaching the configured loopback endpoint; all requests are blocked |
| TLS and other egress | No transparent HTTPS/CONNECT body decryption, QUIC, DNS or arbitrary socket inspection |
| Model requests | Explicit SDK input or recognized routes at the local endpoint; no claim of provider delivery |
| Encodings | Supported bounded representations only; hashing, encryption, truncation and splitting may defeat matching |
| Policy | Exclusions intentionally reduce alert visibility; retained annotations support review |
| Identity | Run/tool labels and local listener observations do not authenticate the actor |
| Durability | Local SQLite, not tamper-evident remote logging; separate filesystem/database crash boundaries |
| Hostile same-user processes | Can bypass integrations, alter state, forge observations, or stop collection |

An SDK read or copy may fail because input exceeds its observation bound. A sink failure is surfaced even if an operation, such as a completed copy, already changed the filesystem. Consumers should not assume an exception rolled back every side effect.

A passive monitor supports one canary registration per inode; additional registrations at the same inode receive explicit diagnostics. Zero watches at readiness is possible for an empty, mismatched, missing, or altered registry. Inspect `MONITOR_HEALTH` and watch counts before interpreting a report.

The local HTTP endpoint is an evaluation and interception boundary, not a general-purpose web service or a system firewall. Configure cooperating applications explicitly. Unsupported framing, limit violations and encrypted tunnels are rejected and diagnosed; they are not recorded as successful clean inspections.

Built-in credentials are nonfunctional. Custom templates are trusted text: their literal content is the operator's responsibility. Default reporting removes synthetic tokens, but the lower-level Event API is not an arbitrary-secret redaction service. Do not put real credentials or raw payloads in custom metadata.

Legitimate tools may access a canary. Review source and provenance before interpreting a sighting as malicious. Sequence and timestamp order support correlation but do not prove causality across processes or sensors.
