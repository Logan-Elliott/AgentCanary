"""State operations must not silently mutate an operator's existing directory."""

import sqlite3
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agentcanary import Store, StoreError
from agentcanary import store as store_module
from agentcanary.filesystem import UnsafePathError


@pytest.mark.parametrize("mode", [0o755, 0o750, 0o777])
def test_existing_nonprivate_state_is_rejected_without_chmod(tmp_path: Path, mode: int) -> None:
    state = tmp_path / "existing"
    state.mkdir()
    state.chmod(mode)
    original = state / "keep.txt"
    original.write_text("operator data")

    with pytest.raises(UnsafePathError, match="state directory must be private"):
        Store(state)

    assert stat.S_IMODE(state.stat().st_mode) == mode
    assert original.read_text() == "operator data"
    assert not (state / "events.sqlite3").exists()


def test_new_state_preserves_parent_permissions(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    parent.chmod(0o755)
    store = Store(parent / "private-state")
    assert stat.S_IMODE(parent.stat().st_mode) == 0o755
    assert stat.S_IMODE(store.state_dir.stat().st_mode) == 0o700
    assert store.events() == []


def test_existing_store_detects_directory_permissions_changed(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    store.state_dir.chmod(0o755)
    with pytest.raises(UnsafePathError, match="state directory must be private"):
        store.events()
    assert stat.S_IMODE(store.state_dir.stat().st_mode) == 0o755


def test_unrelated_database_is_rejected_without_changing_its_journal_mode(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    database = state / "events.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE operator_data (value TEXT)")
        connection.execute("INSERT INTO operator_data VALUES ('keep me')")
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    database.chmod(0o600)
    original = database.read_bytes()

    with pytest.raises(StoreError, match="unrecognized database"):
        Store(state)

    assert database.read_bytes() == original
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("SELECT value FROM operator_data").fetchone() == ("keep me",)


def test_synchronized_store_initialization_after_schema_validation(tmp_path: Path) -> None:
    def initialize(barrier: threading.Barrier, state: Path) -> int:
        barrier.wait()
        return len(Store(state).events())

    with ThreadPoolExecutor(max_workers=2) as pool:
        for attempt in range(20):
            barrier = threading.Barrier(2, timeout=5)
            state = tmp_path / str(attempt)

            futures = [pool.submit(initialize, barrier, state) for _ in range(2)]
            assert [future.result(timeout=15) for future in futures] == [0, 0]


@pytest.mark.parametrize("release_lock", [True, False], ids=["released", "timeout"])
def test_journal_mode_waits_for_competing_writer_with_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release_lock: bool
) -> None:
    state = tmp_path / "state"
    original_connect = sqlite3.connect
    blocker = None
    attempts = 0
    now = 0.0

    class ContendedConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            nonlocal blocker, attempts
            if sql == "PRAGMA journal_mode=WAL":
                attempts += 1
                if blocker is None:
                    blocker = original_connect(state / "events.sqlite3", isolation_level=None)
                    blocker.execute("BEGIN IMMEDIATE")
            return super().execute(sql, *args, **kwargs)

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=ContendedConnection)

    def wait(delay: float) -> None:
        nonlocal now
        assert blocker is not None
        assert 0 < delay <= 0.01
        if release_lock:
            blocker.rollback()
        else:
            now += 10

    monkeypatch.setattr(store_module.sqlite3, "connect", connect)
    monkeypatch.setattr(store_module.time, "monotonic", lambda: now)
    monkeypatch.setattr(store_module.time, "sleep", wait)

    try:
        if release_lock:
            store = Store(state)
            assert store.events() == []
            with original_connect(store.db_path) as connection:
                assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        else:
            with pytest.raises(StoreError) as error:
                Store(state)
            assert error.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_BUSY
        assert attempts == 2
    finally:
        if blocker is not None:
            blocker.close()


def test_journal_mode_does_not_retry_other_sqlite_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_connect = sqlite3.connect

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "PRAGMA journal_mode=WAL":
                return super().execute("SELECT * FROM missing_table")
            return super().execute(sql, *args, **kwargs)

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=FailingConnection)

    monkeypatch.setattr(store_module.sqlite3, "connect", connect)
    monkeypatch.setattr(store_module.time, "sleep", lambda _: pytest.fail("unexpected retry"))

    with pytest.raises(StoreError) as error:
        Store(tmp_path / "state")
    assert error.value.__cause__.sqlite_errorcode == sqlite3.SQLITE_ERROR
