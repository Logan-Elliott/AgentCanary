"""Durable SQLite registry with atomic lifecycle records and independent connections."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from .filesystem import absolute_path, check_private_file, open_directory
from .models import Action, Canary, Event

SCHEMA_VERSION = 1
APPLICATION_ID = 0x41474359
DATABASE_NAME = "events.sqlite3"


class StoreError(RuntimeError):
    """The local evidence store cannot complete the requested operation."""


class Store:
    """Thread/process safe; no connection is shared or retained between operations."""

    def __init__(self, state_dir: str | Path = ".agentcanary") -> None:
        self.state_dir = absolute_path(state_dir)
        self.db_path = self.state_dir / DATABASE_NAME
        fd = open_directory(self.state_dir, create=True, private=True)
        try:
            try:
                db_fd = os.open(
                    DATABASE_NAME,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
            except FileExistsError:
                pass
            else:
                os.fsync(db_fd)
                os.close(db_fd)
                os.fsync(fd)
        finally:
            os.close(fd)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        fd = open_directory(self.state_dir, private=True)
        connection: sqlite3.Connection | None = None
        try:
            check_private_file(fd, DATABASE_NAME)
            for suffix in ("-wal", "-shm", "-journal"):
                check_private_file(fd, DATABASE_NAME + suffix, missing_ok=True)
            # The retained descriptor pins the directory while SQLite opens its files.
            uri = f"file:/proc/self/fd/{fd}/{DATABASE_NAME}?mode=rw"
            connection = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        except sqlite3.Error as exc:
            raise StoreError(f"SQLite operation failed ({type(exc).__name__})") from exc
        finally:
            if connection is not None:
                connection.close()
            os.close(fd)

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                app_id = connection.execute("PRAGMA application_id").fetchone()[0]
                if version == 0:
                    tables = connection.execute("SELECT name FROM sqlite_master").fetchall()
                    if tables or app_id != 0:
                        raise StoreError("refusing to initialize an unrecognized database")
                    connection.execute(
                        "CREATE TABLE canaries (id TEXT PRIMARY KEY, kind TEXT NOT NULL, "
                        "token TEXT NOT NULL UNIQUE, path TEXT NOT NULL, sha256 TEXT NOT NULL, "
                        "created_at TEXT NOT NULL)"
                    )
                    connection.execute(
                        "CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "id TEXT NOT NULL UNIQUE, timestamp TEXT NOT NULL, "
                        "canary_id TEXT REFERENCES canaries(id), action TEXT NOT NULL, "
                        "source TEXT NOT NULL, provenance TEXT NOT NULL, run_id TEXT, pid INTEGER, "
                        "destination TEXT, metadata TEXT NOT NULL)"
                    )
                    connection.execute("CREATE INDEX events_canary ON events(canary_id, seq)")
                    connection.execute("CREATE INDEX events_run ON events(run_id, seq)")
                    connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                elif version != SCHEMA_VERSION or app_id != APPLICATION_ID:
                    raise StoreError("unsupported or unrecognized database schema")
                if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise StoreError("database integrity check failed")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @staticmethod
    def _insert_event(connection: sqlite3.Connection, event: Event) -> Event:
        cursor = connection.execute(
            "INSERT INTO events (id,timestamp,canary_id,action,source,provenance,run_id,pid,"
            "destination,metadata) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                event.id,
                event.timestamp,
                event.canary_id,
                event.action.value,
                event.source,
                event.provenance,
                event.run_id,
                event.pid,
                event.destination,
                json.dumps(dict(event.metadata), allow_nan=False),
            ),
        )
        assert cursor.lastrowid is not None
        return replace(event, seq=cursor.lastrowid)

    def register(self, canary: Canary, *, run_id: str | None = None) -> Event:
        return self.register_many([canary], run_id=run_id)[0]

    def register_many(
        self, canaries: Iterable[Canary], *, run_id: str | None = None
    ) -> list[Event]:
        """Commit a whole seed batch and its CREATE events, or none of them."""
        records = list(canaries)
        events = [
            Event(
                action=Action.CREATE,
                source="generator",
                provenance="direct-write",
                canary_id=canary.id,
                run_id=run_id,
                pid=os.getpid(),
            )
            for canary in records
        ]
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for canary in records:
                    connection.execute(
                        "INSERT INTO canaries (id,kind,token,path,sha256,created_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (
                            canary.id,
                            canary.kind,
                            canary.token,
                            canary.path,
                            canary.sha256,
                            canary.created_at,
                        ),
                    )
                saved = [self._insert_event(connection, event) for event in events]
                connection.commit()
                return saved
            except BaseException:
                connection.rollback()
                raise

    def record(self, event: Event) -> Event:
        if event.seq is not None:
            raise ValueError("cannot ingest an event with an assigned sequence")
        if event.action == Action.CREATE:
            raise ValueError("CREATE events must be paired with registration")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                saved = self._insert_event(connection, event)
                connection.commit()
                return saved
            except BaseException:
                connection.rollback()
                raise

    def canaries(self) -> list[Canary]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM canaries ORDER BY created_at, id").fetchall()
        return [Canary(**dict(row)) for row in rows]

    def get_canary(self, canary_id: str) -> Canary | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM canaries WHERE id=?", (canary_id,)).fetchone()
        return None if row is None else Canary(**dict(row))

    def events(
        self,
        *,
        canary_id: str | None = None,
        action: Action | None = None,
        run_id: str | None = None,
        after_seq: int = 0,
        limit: int | None = None,
    ) -> list[Event]:
        if after_seq < 0 or (limit is not None and limit < 1):
            raise ValueError("after_seq must be nonnegative and limit must be positive")
        query = "SELECT * FROM events WHERE seq > ?"
        values: list[str | int] = [after_seq]
        for field_name, value in (("canary_id", canary_id), ("action", action), ("run_id", run_id)):
            if value is not None:
                query += f" AND {field_name} = ?"
                values.append(value)
        query += " ORDER BY seq"
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)
        with self._connection() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._event_from_row(row) for row in rows]

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> Event:
        data = dict(row)
        data["action"] = Action(data["action"])
        data["metadata"] = json.loads(data["metadata"])
        return Event(**data)
