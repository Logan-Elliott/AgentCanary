import http.client
import json
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from agentcanary import Action, BlockingProxy, InotifyMonitor, Observer, Store, create_canary
from agentcanary.report import render_report


def test_two_canaries_concurrent_sensors_keep_run_boundaries_and_report_roundtrip(
    tmp_path, monkeypatch
):
    store = Store(tmp_path / "state")
    root = tmp_path / "workspace"
    canaries = [
        create_canary(store, root, f"input-{index}", run_id="seed-run") for index in range(2)
    ]
    barrier = threading.Barrier(2)
    connections = []
    original = socket.socket.connect

    def connect(client, address):
        assert address[0] == "127.0.0.1"
        connections.append(address)
        return original(client, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    with (
        InotifyMonitor(store, root, run_id="passive-run") as monitor,
        BlockingProxy(store, run_id="network-run") as proxy,
    ):
        assert monitor.ready.is_set() and monitor.watch_count == 2
        assert proxy.ready.is_set()

        def observe(index):
            observer = Observer(Store(tmp_path / "state"), run_id=f"agent-{index}")
            barrier.wait(timeout=3)
            payload = observer.read(canaries[index].path)
            observer.copy(canaries[index].path, root / f"copy-{index}")
            observer.observe_tool(payload, tool="integration-input")
            observer.observe_embedding(
                payload, destination="https://mock-model.invalid/v1/embeddings"
            )
            body = json.dumps({"input": [canary.token for canary in canaries]}).encode()
            client = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=3)
            try:
                client.request(
                    "POST",
                    "https://mock-model.invalid/v1/embeddings",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
                response = client.getresponse()
                response.read()
                assert response.status == 403
            finally:
                client.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(observe, range(2)))
        deadline = time.monotonic() + 3
        while (
            len(
                {
                    event.canary_id
                    for event in store.events(run_id="passive-run", action=Action.READ)
                }
            )
            != 2
        ):
            monitor.check()
            proxy.check()
            assert time.monotonic() < deadline
            time.sleep(0.005)
        monitor.check()
        proxy.check()
    assert len(connections) == 2
    for index, canary in enumerate(canaries):
        agent = store.events(run_id=f"agent-{index}")
        assert len(agent) == 4
        assert all(event.canary_id == canary.id and event.pid == os.getpid() for event in agent)
        network = [event for event in store.events(canary_id=canary.id) if event.source == "http"]
        assert len(network) == 4
        assert all(event.run_id == "network-run" and event.pid is None for event in network)
        passive = [
            event for event in store.events(canary_id=canary.id) if event.source == "inotify"
        ]
        assert passive and all(
            event.run_id == "passive-run" and event.pid is None for event in passive
        )
    events = store.events()
    assert len({event.seq for event in events}) == len(events)
    report = render_report(events, format="jsonl", canaries=store.canaries())
    decoded = [json.loads(line) for line in report.splitlines()]
    assert [item["seq"] for item in decoded] == [event.seq for event in events]
    assert all(canary.token not in report for canary in canaries)
