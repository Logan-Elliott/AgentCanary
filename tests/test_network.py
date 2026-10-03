import gzip
import http.client
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from agentcanary import Action, BlockingProxy, NetworkError, Store, create_canary


@pytest.fixture
def issued(tmp_path):
    store = Store(tmp_path / "state")
    return store, create_canary(store, tmp_path / "workspace", "token")


def exchange(proxy, wire, *, shutdown=True):
    with socket.socket() as client:
        client.settimeout(3)
        client.connect((proxy.host, proxy.port))
        client.sendall(wire)
        if shutdown:
            client.shutdown(socket.SHUT_WR)
        response = b""
        while chunk := client.recv(4096):
            response += chunk
        return int(response.split(b" ")[1]), response


def post(proxy, target, body, headers=None):
    connection = http.client.HTTPConnection(proxy.host, proxy.port, timeout=3)
    try:
        connection.request("POST", target, body=body, headers=headers or {})
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.005)


def test_real_http_proxy_never_resolves_or_connects_upstream(issued, monkeypatch, capsys):
    store, canary = issued
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    resolved = []
    connected = []

    def only_loopback_resolve(host, *args, **kwargs):
        resolved.append(host)
        assert host == "127.0.0.1", "upstream DNS is forbidden"
        return original_resolve(host, *args, **kwargs)

    def only_loopback_connect(sock, address):
        connected.append(address)
        assert address[0] == "127.0.0.1", "upstream connections are forbidden"
        return original_connect(sock, address)

    monkeypatch.setattr(socket, "getaddrinfo", only_loopback_resolve)
    monkeypatch.setattr(socket.socket, "connect", only_loopback_connect)
    with BlockingProxy(store, run_id="operator") as proxy:
        assert proxy.ready.is_set()
        assert proxy.running
        target = "https://user:PRIVATE_PASSWORD@upstream.invalid/v1/embeddings?key=PRIVATE_QUERY"
        assert (
            post(
                proxy,
                target,
                json.dumps({"input": canary.token}),
                {
                    "Authorization": "Bearer PRIVATE_HEADER",
                    "X-Pid": str(os.getpid()),
                    "X-Run-Id": "PRIVATE_RUN",
                },
            )
            == 403
        )
        assert post(proxy, "/v1/messages", canary.token) == 403
        assert post(proxy, "http://upstream.invalid/private-path", "ordinary") == 403
        proxy.check()
    assert not proxy.ready.is_set()
    assert not proxy.running
    events = store.events(action=Action.EXFILTRATION)
    assert len(events) == 2
    assert len(store.events(action=Action.MODEL_REQUEST)) == 2
    assert all(event.pid is None and event.run_id == "operator" for event in events)
    assert events[0].destination == "https://upstream.invalid"
    assert all(event.metadata["blocked"] is True for event in events)
    assert resolved == ["127.0.0.1"] * 3
    assert len(connected) == 3
    assert "PRIVATE_" not in repr(store.events())
    assert canary.token not in repr(store.events())
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "fragment,status,reason",
    [
        (
            b"CONNECT upstream.invalid:443 HTTP/1.1\r\nHost: upstream.invalid\r\n\r\n",
            501,
            "tls_tunnel_unsupported",
        ),
        (
            b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n",
            501,
            "unsupported_transfer_encoding",
        ),
        (
            b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\nx",
            400,
            "ambiguous_headers",
        ),
        (b"GET / HTTP/1.1\r\nHost: x\r\nHost: y\r\n\r\n", 400, "ambiguous_headers"),
        (b"GET / HTTP/1.1\r\nHost: x\r\n folded\r\n\r\n", 400, "invalid_header"),
        (b"GET / HTTP/1.1\r\nHost: x\r\nContent-Length : 0\r\n\r\n", 400, "invalid_header"),
        (
            b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: +1\r\n\r\n",
            400,
            "invalid_content_length",
        ),
        (b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 99\r\n\r\nx", 400, "incomplete_body"),
        (b"GET / HTTP/1.1\r\nHost: x", 400, "incomplete_headers"),
        (b"GET / HTTP/1.1\r\nHost: x\r\n\r\nunframed", 400, "unexpected_trailing_data"),
        (b"GET / HTTP/1.1\r\n\r\n", 400, "missing_host"),
        (b"INVALID PRIVATE_CONTENT\r\n\r\n", 400, "invalid_request_line"),
        (b"GET ftp://x/ HTTP/1.1\r\nHost: x\r\n\r\n", 400, "invalid_request_target"),
        (
            b"POST / HTTP/1.1\r\nHost: x\r\nExpect: 100-continue\r\n\r\n",
            417,
            "unsupported_expectation",
        ),
    ],
)
def test_explicit_framing_rejections(issued, fragment, status, reason, capsys):
    store, _ = issued
    with BlockingProxy(store) as proxy:
        actual, response = exchange(proxy, fragment)
        assert actual == status
        assert b"PRIVATE_CONTENT" not in response
        proxy.check()
    health = store.events(action=Action.MONITOR_HEALTH)
    assert health[-1].metadata["reason"] == reason
    assert not store.events(action=Action.EXFILTRATION)
    assert capsys.readouterr() == ("", "")


def test_body_header_and_gzip_bounds(issued):
    store, canary = issued
    with BlockingProxy(store, max_body_bytes=256, max_header_bytes=256) as proxy:
        assert post(proxy, "http://sink.invalid/", canary.token) == 403
        assert (
            post(
                proxy,
                "http://sink.invalid/",
                gzip.compress(canary.token.encode()),
                {"Content-Encoding": "gzip"},
            )
            == 403
        )
        assert (
            post(
                proxy,
                "http://sink.invalid/",
                gzip.compress(b"x" * 10000),
                {"Content-Encoding": "gzip"},
            )
            == 413
        )
        assert post(proxy, "/", b"x" * 257) == 413
        code, _ = exchange(proxy, b"GET / HTTP/1.1\r\nHost: x\r\nX: " + b"s" * 256)
        assert code == 431
    reasons = {event.metadata["reason"] for event in store.events(action=Action.MONITOR_HEALTH)}
    assert reasons == {"gzip_limit", "body_limit", "header_limit"}
    assert len(store.events(action=Action.EXFILTRATION)) == 2


def test_worker_limit_deadline_and_shutdown(issued):
    store, _ = issued
    proxy = BlockingProxy(store, max_workers=1, read_timeout=0.2)
    proxy.start()
    with socket.create_connection((proxy.host, proxy.port), timeout=2) as slow:
        slow.sendall(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 10\r\n\r\nx")
        wait_for(lambda: len(proxy._workers) == 1)
        code, _ = exchange(proxy, b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        assert code == 503
        assert b"408" in slow.recv(4096)
    proxy.stop()
    proxy.stop()
    assert not proxy._workers
    reasons = {event.metadata["reason"] for event in store.events(action=Action.MONITOR_HEALTH)}
    assert reasons == {"worker_limit", "read_timeout"}
    proxy.start()
    with socket.create_connection((proxy.host, proxy.port), timeout=2) as slow:
        slow.sendall(b"GET / HTTP/1.1\r\n")
        wait_for(lambda: len(proxy._workers) == 1)
        before = time.monotonic()
        proxy.stop()
        assert time.monotonic() - before < 1
        assert not proxy._workers


def test_concurrent_real_requests_are_retained_once(issued):
    store, canary = issued
    with BlockingProxy(store, max_workers=16) as proxy:
        with ThreadPoolExecutor(max_workers=8) as executor:
            statuses = list(
                executor.map(lambda _: post(proxy, "/v1/responses", canary.token), range(24))
            )
        assert statuses == [403] * 24
        proxy.check()
    assert len(store.events(action=Action.EXFILTRATION)) == 24
    assert len(store.events(action=Action.MODEL_REQUEST)) == 24


@pytest.mark.parametrize("error", [ValueError, OSError, RuntimeError])
def test_sink_failures_stop_listener_without_reflection(issued, error, capsys):
    store, canary = issued

    class FailedSink:
        def record(self, event):
            raise error("PRIVATE_SINK_CONTENT")

    proxy = BlockingProxy(store, sink=FailedSink())
    proxy.start()
    code = post(proxy, "http://sink.invalid/", canary.token)
    assert code == 500
    with pytest.raises(NetworkError, match="failure"):
        proxy.check()
    with pytest.raises(NetworkError, match="failure"):
        proxy.stop()
    assert not proxy.running
    assert not proxy._workers
    assert capsys.readouterr() == ("", "")


def test_empty_registry_and_validation_are_explicit(tmp_path):
    store = Store(tmp_path / "empty")
    with BlockingProxy(store) as proxy:
        assert post(proxy, "/", "AGENTCANARY_SYNTHETIC_" + "0" * 32) == 403
    assert store.events(action=Action.MONITOR_HEALTH)[0].metadata["reason"] == "empty_registry"
    for kwargs in (
        {"host": "localhost"},
        {"host": "0.0.0.0"},
        {"host": "192.0.2.1"},
        {"port": True},
        {"port": -1},
        {"max_workers": 0},
        {"read_timeout": float("nan")},
    ):
        with pytest.raises(ValueError):
            BlockingProxy(store, **kwargs)


@pytest.mark.parametrize("ending", ["duration", "term", "interrupt"])
def test_proxy_cli_readiness_and_lifecycle(issued, tmp_path, ending):
    store, canary = issued
    command = [
        sys.executable,
        "-m",
        "agentcanary",
        "--state-dir",
        str(store.state_dir),
        "serve",
        "--port",
        "0",
        "--run-id",
        "cli-test",
    ]
    if ending == "duration":
        command += ["--duration", "0.4"]
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([child.stdout], [], [], 5)[0]
        ready = json.loads(child.stdout.readline())
        assert ready["mode"] == "always_block"
        port = int(ready["url"].rsplit(":", 1)[1])
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request("POST", "/v1/responses", body=canary.token)
        assert connection.getresponse().status == 403
        connection.close()
        if ending != "duration":
            child.send_signal(signal.SIGTERM if ending == "term" else signal.SIGINT)
        stdout, stderr = child.communicate(timeout=5)
        assert child.returncode == (130 if ending == "interrupt" else 0)
        assert not stdout
        assert stderr == ("agentcanary: interrupted\n" if ending == "interrupt" else "")
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
    assert len(store.events(action=Action.MODEL_REQUEST)) == 1
