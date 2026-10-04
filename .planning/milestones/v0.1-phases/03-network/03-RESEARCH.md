# HTTP inspection research

HTTP message framing and connection lifetime require explicit bounds. Treat framing ambiguity and unsupported transfer encodings as rejected, uninspected input. A loopback blocking endpoint can inspect complete HTTP input without implementing an upstream forwarding stack. CONNECT cannot reveal encrypted request bodies; record this limitation instead of claiming coverage.

Python http.server supplies parsing primitives but is not a hardened general-purpose deployment server. If used, bound headers, body, read time and worker count, suppress default raw request/error logging, close connections deterministically, and surface server/sink failures. gzip decoding should use bounded zlib streaming/decompress limits and validate eof/trailing data; avoid unbounded gzip.decompress on request input.

Sources:
- https://www.rfc-editor.org/rfc/rfc9112.html (message framing and incomplete requests)
- https://docs.python.org/3/library/http.server.html (HTTP server primitives and caveats)
- https://docs.python.org/3/library/zlib.html (bounded streaming decompression)

Registry-backed marker matching avoids generic credential pattern alerts. JSON/base64/URL normalization must remain bounded, identify decoded representation, and avoid recording transformed payloads. Explicit pre-TLS SDK observation covers cooperating HTTPS clients without claims of passive TLS visibility.
