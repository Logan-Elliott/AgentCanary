# Threat model

AgentCanary records interactions with synthetic artifacts inside an operator-controlled agent workspace. Its security value is attributable evidence within declared observation boundaries. It is not a sandbox, a general data-loss prevention system, or a guarantee that an agent cannot transmit data.

## Assets and trust boundaries

| Asset or boundary | Required property |
| --- | --- |
| Issued canary registry | Unique identifiers and markers; creation paired with a durable event |
| Seeded workspace | Preserve existing files; refuse traversal, symlinks, and destination collisions |
| Event store | Ordered, locally durable records; private filesystem permissions; no raw payload storage |
| Instrumented application | Accurate caller/run provenance; errors surfaced rather than silently losing evidence |
| Linux monitor | Real access observations; no invented process identity; explicit coverage-loss diagnostics |
| Local HTTP inspection endpoint | Bounded parsing, loopback binding, no upstream forwarding; requests described as attempts |
| Operator configuration | Explicit scope and exclusions; invalid or misspelled settings rejected |

The operator chooses a workspace and a private state directory. Prefer a state directory outside the agent's writable workspace. Filesystem mode 0700 protects state from other ordinary accounts; it does not protect it from another process using the same account or from root.

## Threats in scope

- An agent reads an artifact, copies or embeds its issued marker, passes it to a tool, or includes it in a model/API request through a configured observation boundary.
- Ordinary tools accidentally propagate synthetic credential-like values into arguments, standard input, HTTP headers, URLs, or bodies.
- Concurrent local writers, unexpected process exits, file replacement, watch invalidation, queue overflow, malformed requests, oversized inputs, and I/O failures interrupt evidence collection.
- Innocent operator mistakes select an existing file, an unrelated database, a nonprivate state directory, or a path outside the intended seed destinations.

Built-in values are explicitly synthetic and nonfunctional. Provider-like values use invalid credential syntax, SSH artifacts contain no valid private key, and service names use reserved `.invalid` destinations. Custom templates are trusted operator-authored text; substitution is inert, but the framework cannot certify arbitrary literal content the operator supplies. Never place real credentials in templates or demonstration fixtures.

## Evidence and attribution

A marker sighting establishes that an issued marker was present at the observation point. It does not establish malicious intent, whether a model understood the value, or whether the destination received it.

Each record identifies its observation source and provenance. SQLite sequence numbers give ingestion order, while timestamps give observation time. A shared canary ID and run label support correlation; they are not cryptographic proof of causality. Independent sources can describe the same operation and intentionally remain separate events.

- Linux inotify does not identify the originating process. A filesystem-only READ has an unknown PID and is evidence of access to the watched inode, not a byte count or semantic read.
- SDK observations identify the calling process. A tool-input observation identifies supplied input or an invocation attempt, not proof that the child consumed the input. Operator-supplied names and run labels are correlation hints.
- An HTTP listener observes requests reaching that listener. It cannot reliably identify a remote client's OS PID and must not trust a request header as process identity.
- EXFILTRATION describes an observed transmission attempt. The local blocking endpoint does not establish upstream delivery.

## Controls and failure behavior

Creation uses exclusive opens and directory-relative no-follow operations. Ordinary failures trigger best-effort cleanup of newly created artifacts while preserving existing files. Cleanup resources are reserved before mutations. Filesystem writes and SQLite transactions are separate durability boundaries: a process crash or filesystem failure can leave an unregistered file. Inspect a failed workspace before reseeding; AgentCanary does not automatically delete unknown files.

The store checks application/schema identity before persistent database configuration. Existing nonprivate state directories are rejected without changing their permissions. SQLite transactions, foreign keys, WAL, busy timeout, and separate connections support concurrent local writers. Disk-full, permission, and sink failures are surfaced. Local durability is not tamper evidence or an independent audit log.

Input size and parsing limits bound observation work. Limit violations and coverage loss must be explicit, never interpreted as a clean scan. Request bodies, authorization headers, raw arguments, environment values, and tool output must not be persisted as event evidence. Event adapters sanitize metadata before recording it; the low-level Event API is not a general-purpose secret scrubber.

## Out of scope and residual risks

- A hostile process with the monitoring account's privileges can alter artifacts or state, kill monitors, forge observations, bypass the SDK, or use another network path. Use separate accounts, sandboxing, filesystem protections, and independent enforcement when those guarantees are needed.
- Direct sockets, alternative proxies, encrypted TLS/QUIC payloads, and traffic that bypasses the configured adapter remain outside HTTP inspection. Blocking a local proxy request does not block all egress from the machine.
- Truncation, hashing, encryption, splitting a marker across operations, unsupported encodings, or transformations beyond the decoder budget can prevent matching. Absence of a marker event is not evidence of safe behavior.
- Inotify can coalesce events or overflow, and it does not observe all access mechanisms. Snapshot monitoring has startup and replacement windows; explicit health events describe known coverage changes, not every possible missed event.
- Another local process can submit synthetic tokens to a local listener and generate events. Listener provenance does not authenticate an agent's identity.
- Legitimate indexing, editors, backups, security tools, and test processes can access canaries. These observations are not automatically malicious. Configuration exclusions reduce noise but create deliberate gaps.
- Host compromise, root/kernel tampering, forensic integrity, distributed clocks, and long-term retention are outside this release's guarantees.

## Extension constraints

Future auditd/eBPF monitors should preserve source-specific attribution, permission requirements, loss indicators, and common event identifiers. A new event sink must document its durability and failure semantics. A model integration should observe the exact request input before TLS and avoid logging unrelated content. Additional decoding must remain bounded and identify the representation that matched.

## Verification

The release verification maps these controls to automated tests and the local end-to-end demonstration. The final review covers false positives/negatives, path and process attribution, concurrency, synthetic-secret handling, network blind spots, portability, and installation. Tests use only synthetic artifacts and local processes; application network tests stay on loopback.

## References

- [Linux inotify API and limitations](https://man7.org/linux/man-pages/man7/inotify.7.html)
- [Python audit-hook security limits](https://docs.python.org/3/library/sys.html#sys.addaudithook)
- [Python SQLite transaction and connection behavior](https://docs.python.org/3/library/sqlite3.html)
