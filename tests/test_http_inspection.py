import base64
import gzip
import json
import os
from urllib.parse import quote

import pytest

from agentcanary import (
    Action,
    DecodeError,
    HTTPInspector,
    Observer,
    PayloadTooLarge,
    Store,
    TokenMatcher,
    create_canary,
)
from agentcanary.network import model_route, safe_origin


@pytest.fixture
def issued(tmp_path):
    store = Store(tmp_path / "state")
    canary = create_canary(store, tmp_path / "workspace", "token")
    return store, canary


@pytest.mark.parametrize(
    "encoding", ["plain", "percent", "json", "base64", "urlsafe", "nested", "form"]
)
def test_bounded_common_representations(issued, encoding):
    store, canary = issued
    token = canary.token
    variants = {
        "plain": "prefix" + token + token + "deadbeef",
        "percent": "".join(f"%{ord(c):02x}" for c in token),
        "json": '{"content":"' + "".join(f"\\u{ord(c):04x}" for c in token) + '"}',
        "base64": base64.b64encode(token.encode()),
        "urlsafe": base64.urlsafe_b64encode((">>>" + token + "???").encode()).rstrip(b"="),
        "nested": json.dumps({"payload": base64.b64encode(token.encode()).decode()}),
        "form": "data=" + quote(base64.b64encode(token.encode()).decode(), safe=""),
    }
    result = TokenMatcher(store.canaries()).match_encoded([variants[encoding]])
    assert [match.canary for match in result.matches] == [canary]
    assert result.bytes_scanned >= len(variants[encoding])
    assert token not in repr(result)


def test_field_boundaries_negative_controls_and_dedup(issued):
    store, canary = issued
    matcher = TokenMatcher(store.canaries())
    assert not matcher.match_encoded([canary.token[:25], canary.token[25:]]).matches
    assert not matcher.match_encoded([canary.token[:-1]]).matches
    assert not matcher.match_encoded(["AGENTCANARY_SYNTHETIC_" + "0" * 32]).matches
    assert not matcher.match_encoded([canary.token.replace("SYNTHETIC", "CHANGED")]).matches
    result = matcher.match_encoded([canary.token, base64.b64encode(canary.token.encode())])
    assert len(result.matches) == 1
    assert result.matches[0].encoding == "plaintext"


def test_decoding_limits_and_invalid_inputs_are_visible(issued):
    store, canary = issued
    matcher = TokenMatcher(store.canaries(), max_bytes=1024)
    with pytest.raises(PayloadTooLarge):
        matcher.match_encoded([b"x" * 600, b"y" * 600])
    for parts, kwargs, reason in [
        ([base64.b64encode(canary.token.encode())], {"max_depth": 0}, "decode_depth"),
        ([b"one", b"two"], {"max_candidates": 1}, "decode_candidates"),
        ([canary.token], {"max_work_bytes": 1}, "decode_bytes"),
        ([b'{"a":'], {}, "invalid_json"),
        ([b'"\\ud800"'], {}, "invalid_json_unicode"),
        ([json.dumps(["a"] * 150)], {"max_candidates": 128}, "json_nodes"),
    ]:
        with pytest.raises(DecodeError, match=reason):
            matcher.match_encoded(parts, **kwargs)
    observer = Observer(store, max_bytes=128)
    with pytest.raises(PayloadTooLarge):
        observer.observe_model("x" * 129, destination="https://model.invalid/v1/responses")
    assert store.events(action=Action.MONITOR_HEALTH)[-1].metadata["reason"] == "payload_limit"


def test_sdk_http_model_and_embedding_preserve_honest_provenance(issued):
    store, canary = issued
    observer = Observer(store, run_id="sdk-http")
    url = "https://user:PRIVATE_PASSWORD@MODEL.invalid:443/v1/chat/completions?key=PRIVATE_QUERY"
    events = observer.observe_http(
        "POST",
        url,
        headers={"Authorization": "Bearer PRIVATE_HEADER"},
        body=json.dumps({"messages": [{"content": canary.token}], "model": "PRIVATE_MODEL"}),
    )
    assert {event.action for event in events} == {Action.EXFILTRATION, Action.MODEL_REQUEST}
    for event in events:
        assert event.destination == "https://model.invalid"
        assert event.pid == os.getpid()
        assert event.run_id == "sdk-http"
        assert event.source == "sdk"
        assert event.metadata["blocked"] is False
        assert event.provenance == "sdk_http_input"
    for method, operation in [
        (observer.observe_model, "model_input"),
        (observer.observe_embedding, "embedding_input"),
    ]:
        (event,) = method(canary.token, destination="https://model.invalid/v1/embeddings")
        assert event.action == Action.MODEL_REQUEST
        assert event.metadata["operation"] == operation
        assert event.metadata["attribution"] == "caller_pid"
    assert "PRIVATE_" not in repr(store.events())
    assert canary.token not in repr(store.events())


def test_direct_http_fields_gzip_and_route_classification(issued):
    store, canary = issued
    inspector = HTTPInspector(store, run_id="listener")
    for body, headers, target in [
        (b"", {"Host": "sink.invalid", "X-Test": canary.token}, "/private-path"),
        (b"", {"Host": "sink.invalid"}, "/private?key=" + canary.token),
        (
            gzip.compress(canary.token.encode()),
            {"Content-Encoding": "gzip"},
            "https://sink.invalid/v1/responses",
        ),
    ]:
        events = inspector.inspect("POST", target, headers=headers, body=body, blocked=True)
        assert events[0].pid is None
        assert events[0].run_id == "listener"
        assert events[0].metadata["blocked"] is True
        assert events[0].destination in ("http://sink.invalid", "https://sink.invalid")
    assert len(store.events(action=Action.MODEL_REQUEST)) == 1
    assert model_route("https://openai.invalid/arbitrary?q=/v1/responses") is None
    assert model_route("https://x.invalid/v1/%65mbeddings/?secret") == "/v1/embeddings"
    assert "private" not in repr(store.events(action=Action.EXFILTRATION))


@pytest.mark.parametrize(
    "body,encoding,reason",
    [
        (b"invalid", "gzip", "invalid_gzip"),
        (gzip.compress(b"x" * 1000), "gzip", "gzip_limit"),
        (gzip.compress(b"x")[:-1], "gzip", "invalid_gzip"),
        (gzip.compress(b"x") + gzip.compress(b"y"), "gzip", "invalid_gzip"),
        (b"x", "br", "unsupported_content_encoding"),
    ],
)
def test_failed_body_decoding_records_health(issued, body, encoding, reason):
    store, _ = issued
    with pytest.raises(DecodeError, match=reason):
        HTTPInspector(store, max_bytes=256).inspect(
            "POST", "http://sink.invalid/", headers={"Content-Encoding": encoding}, body=body
        )
    assert store.events(action=Action.MONITOR_HEALTH)[-1].metadata["reason"] == reason
    assert not store.events(action=Action.EXFILTRATION)


def test_safe_origin_validation_and_snapshot_refresh(issued):
    store, canary = issued
    assert (
        safe_origin("https://name:password@EXAMPLE.invalid:443/private?q=secret#hidden")
        == "https://example.invalid"
    )
    assert safe_origin("http://[::1]:8888/private") == "http://[::1]:8888"
    assert canary.token.lower() not in safe_origin("http://" + canary.token + ".invalid")
    for url in (
        "file:///etc/passwd",
        "//sink.invalid",
        "https://bad:99999",
        "http://bad%00.invalid",
        "http://x\n.invalid",
    ):
        with pytest.raises(ValueError, match="valid HTTP"):
            safe_origin(url)
    observer = Observer(store)
    new = create_canary(store, store.state_dir.parent / "workspace", "later")
    assert not observer.observe_model(new.token, destination="http://model.invalid")
    observer.refresh()
    assert observer.observe_model(new.token, destination="http://model.invalid")
