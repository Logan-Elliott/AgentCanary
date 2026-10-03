import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest

from agentcanary import Action, Canary, Event, EventSink, Store, StoreError
from agentcanary.filesystem import UnsafePathError


def canary(path: str = "/workspace/example") -> Canary:
    return Canary(
        kind="env", token="AGENTCANARY_SYNTHETIC_" + uuid4().hex, path=path, sha256="0" * 64
    )


def test_round_trip_and_atomicity(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    item = canary()
    created = store.register(item, run_id="run-a")
    assert isinstance(store, EventSink)
    assert created.seq == 1
    assert store.get_canary(item.id) == item
    assert store.get_canary(str(uuid4())) is None
    assert store.events() == [created]
    duplicate = canary()
    with pytest.raises(StoreError):
        store.register_many([duplicate, item])
    assert store.canaries() == [item]
    assert len(store.events()) == 1
    read = store.record(Event(action=Action.READ, source="sdk", canary_id=item.id, pid=os.getpid()))
    assert read.seq == 2
    assert Store(tmp_path / "state").events(after_seq=1, action=Action.READ) == [read]
    with pytest.raises(StoreError):
        store.record(Event(action=Action.READ, source="sdk", canary_id=str(uuid4())))
    with pytest.raises(ValueError):
        store.record(created)
    with pytest.raises(ValueError):
        store.record(Event(action=Action.CREATE, source="sdk", canary_id=item.id))


def test_immutable_bounded_metadata() -> None:
    metadata = {"reason": "safe"}
    event = Event(action=Action.MONITOR_HEALTH, source="test", metadata=metadata)
    metadata["reason"] = "changed"
    assert event.metadata["reason"] == "safe"
    with pytest.raises(TypeError):
        event.metadata["reason"] = "changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        event.pid = 3  # type: ignore[misc]
    for metadata in ({"body": "do not log"}, {"reason": "x" * 513}, {"count": float("nan")}):
        with pytest.raises(ValueError):
            Event(action=Action.MONITOR_HEALTH, source="test", metadata=metadata)
    with pytest.raises(ValueError):
        Event(action=Action.READ, source="test")
    with pytest.raises(ValueError):
        Event(action=Action.MONITOR_HEALTH, source="test", pid=0)


def test_private_state_and_symlink_rejection(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    assert store.state_dir.stat().st_mode & 0o777 == 0o700
    assert store.db_path.stat().st_mode & 0o777 == 0o600
    (tmp_path / "link").symlink_to(store.state_dir, target_is_directory=True)
    with pytest.raises(OSError):
        Store(tmp_path / "link")
    (store.state_dir / "events.sqlite3-wal").symlink_to(tmp_path / "victim")
    with pytest.raises(UnsafePathError):
        store.events()
    assert not (tmp_path / "victim").exists()


def test_corruption_and_version_validation(tmp_path: Path) -> None:
    store = Store(tmp_path / "version")
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(StoreError, match="schema"):
        Store(store.state_dir)
    other = Store(tmp_path / "corrupt")
    other.db_path.write_bytes(b"not a SQLite database")
    with pytest.raises(StoreError):
        Store(other.state_dir)


def test_concurrent_threads(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    records = [canary(f"/workspace/{i}") for i in range(30)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(store.register, records))
    assert len(store.canaries()) == 30
    assert [event.seq for event in store.events()] == list(range(1, 31))


def test_database_links_and_unrecognized_schema_are_rejected(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    target = tmp_path / "untouched"
    target.write_text("keep")
    (state / "events.sqlite3").symlink_to(target)
    with pytest.raises(UnsafePathError):
        Store(state)
    assert target.read_text() == "keep"
    (state / "events.sqlite3").unlink()
    target.chmod(0o600)
    os.link(target, state / "events.sqlite3")
    with pytest.raises(UnsafePathError):
        Store(state)
    (state / "events.sqlite3").unlink()
    with sqlite3.connect(state / "events.sqlite3") as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    (state / "events.sqlite3").chmod(0o600)
    with pytest.raises(StoreError, match="unrecognized"):
        Store(state)


def test_query_parameters_and_sequence_limits(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    item = canary()
    store.register(item, run_id="first")
    store.record(Event(action=Action.READ, source="sdk", canary_id=item.id, run_id="second"))
    assert len(store.events(limit=1)) == 1
    assert len(store.events(canary_id=item.id, action=Action.READ, run_id="second")) == 1
    assert store.events(canary_id="' OR 1=1 --") == []
    assert store.get_canary("' OR 1=1 --") is None
    with pytest.raises(ValueError):
        store.events(after_seq=-1)
    with pytest.raises(ValueError):
        store.events(limit=0)
