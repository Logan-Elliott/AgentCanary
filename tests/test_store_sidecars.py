"""Optional SQLite sidecar unlink races must not weaken state-file validation."""

import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from agentcanary import Action, Event, Store
from agentcanary import filesystem as fs

SIDECARS = ("events.sqlite3-wal", "events.sqlite3-shm", "events.sqlite3-journal")


def sample(*, links=0, mode=stat.S_IFREG | 0o600, uid=None):
    return SimpleNamespace(st_nlink=links, st_mode=mode, st_uid=os.getuid() if uid is None else uid)


def stat_sequence(monkeypatch, name, outcomes):
    original = os.stat
    remaining = iter(outcomes)
    calls = []

    def checked(path, *args, **kwargs):
        if path == name and kwargs.get("dir_fd") == 12345:
            assert kwargs["follow_symlinks"] is False
            calls.append(path)
            outcome = next(remaining)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return original(path, *args, **kwargs)

    monkeypatch.setattr(fs.os, "stat", checked)
    return calls


@pytest.mark.parametrize("name", SIDECARS)
@pytest.mark.parametrize("recreated", [False, True])
def test_optional_deleted_sidecar_is_rechecked_until_missing_or_safe(monkeypatch, name, recreated):
    replacement = sample(links=1) if recreated else FileNotFoundError()
    calls = stat_sequence(monkeypatch, name, [sample(), replacement])
    fs.check_private_file(12345, name, missing_ok=True)
    assert len(calls) == 2


def test_repeated_unlink_samples_have_a_finite_retry_bound(monkeypatch):
    name = SIDECARS[0]
    calls = stat_sequence(monkeypatch, name, [sample()] * 3 + [sample(links=1)])
    with pytest.raises(fs.UnsafePathError):
        fs.check_private_file(12345, name, missing_ok=True)
    assert len(calls) == 3


def test_last_bounded_attempt_still_validates_recreated_sidecar(monkeypatch):
    name = SIDECARS[1]
    calls = stat_sequence(monkeypatch, name, [sample(), sample(), sample(links=1)])
    fs.check_private_file(12345, name, missing_ok=True)
    assert len(calls) == 3


@pytest.mark.parametrize(
    "name,missing_ok",
    [
        ("events.sqlite3", False),
        ("events.sqlite3", True),
        ("unrelated.sqlite3-wal", True),
        ("cache.tmp", True),
        ("events.sqlite3-shm", False),
    ],
)
def test_zero_link_primary_or_unrelated_file_is_never_retried(monkeypatch, name, missing_ok):
    calls = stat_sequence(monkeypatch, name, [sample(), sample(links=1)])
    with pytest.raises(fs.UnsafePathError):
        fs.check_private_file(12345, name, missing_ok=missing_ok)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "unsafe",
    [
        sample(links=2),
        sample(mode=stat.S_IFLNK | 0o600),
        sample(mode=stat.S_IFDIR | 0o600),
        sample(uid=os.getuid() + 1),
        sample(mode=stat.S_IFREG | 0o644),
    ],
    ids=["hardlink", "symlink", "directory", "foreign-owner", "public-mode"],
)
@pytest.mark.parametrize("after_unlink", [False, True])
def test_unsafe_attributes_are_rejected_before_any_retry(monkeypatch, unsafe, after_unlink):
    name = SIDECARS[0]
    prefix = [sample()] if after_unlink else []
    calls = stat_sequence(monkeypatch, name, prefix + [unsafe, sample(links=1)])
    with pytest.raises(fs.UnsafePathError):
        fs.check_private_file(12345, name, missing_ok=True)
    assert len(calls) == 1 + int(after_unlink)


def test_revalidation_does_not_swallow_unrelated_filesystem_errors(monkeypatch):
    name = SIDECARS[1]
    calls = stat_sequence(monkeypatch, name, [sample(), PermissionError()])
    with pytest.raises(PermissionError):
        fs.check_private_file(12345, name, missing_ok=True)
    assert len(calls) == 2


def test_missing_primary_database_still_fails(monkeypatch):
    name = "events.sqlite3"
    stat_sequence(monkeypatch, name, [FileNotFoundError()])
    with pytest.raises(FileNotFoundError):
        fs.check_private_file(12345, name)


def test_real_concurrent_store_connections_preserve_all_writes_during_sidecar_churn(tmp_path):
    stores = [Store(tmp_path / "state") for _ in range(4)]
    barrier = threading.Barrier(4, timeout=5)

    def read_write(index):
        barrier.wait()
        store = stores[index]
        for _ in range(200):
            if index < 2:
                store.record(
                    Event(action=Action.MONITOR_HEALTH, source="test", run_id=f"writer-{index}")
                )
            else:
                store.events(limit=10)

    def read_only(index):
        barrier.wait()
        for _ in range(400):
            stores[index].events(limit=10)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(read_write, range(4)))
        # Read-only connections also create/remove WAL sidecars on open/last-close.
        list(pool.map(read_only, range(4)))
    events = stores[0].events()
    assert len(events) == 400
    assert len({event.id for event in events}) == 400
    assert [event.seq for event in events] == list(range(1, 401))
    assert len(stores[1].events(run_id="writer-0")) == 200
    assert len(stores[2].events(run_id="writer-1")) == 200
