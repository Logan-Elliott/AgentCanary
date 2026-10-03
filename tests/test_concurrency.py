import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from agentcanary import Action, Event, Store, create_canary


def _writer(state: str, worker: int) -> int:
    store = Store(state)
    for index in range(12):
        store.record(
            Event(
                action=Action.MONITOR_HEALTH,
                source="process-test",
                run_id=f"worker-{worker}",
                metadata={"count": index},
            )
        )
    return 12


def test_concurrent_process_initialization_and_writes(tmp_path: Path) -> None:
    state = str(tmp_path / "state")
    with ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        assert sum(pool.map(_writer, [state] * 4, range(4))) == 48
    store = Store(state)
    assert [event.seq for event in store.events()] == list(range(1, 49))
    assert len({event.id for event in store.events()}) == 48
    assert len(store.events(run_id="worker-2")) == 12


def test_concurrent_same_destination_never_overwrites(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def attempt(_: int) -> bool:
        try:
            create_canary(store, workspace, "artifact.env")
        except FileExistsError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(attempt, range(2))) == 1
    assert len(store.canaries()) == 1
    assert len(store.events()) == 1
    assert store.canaries()[0].token in (workspace / "artifact.env").read_text()
