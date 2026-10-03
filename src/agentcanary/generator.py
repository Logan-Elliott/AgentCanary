"""Safe artifact creation with batch preflight and ordinary-failure rollback."""

from __future__ import annotations

import os
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .filesystem import UnsafePathError, absolute_path, open_directory
from .models import Canary
from .store import Store
from .templates import generate


@dataclass(frozen=True, slots=True)
class SeedSpec:
    path: str
    kind: str
    template: str | None = None


PROFILES: dict[str, tuple[SeedSpec, ...]] = {
    "minimal": (SeedSpec(".env", "env"), SeedSpec(".aws/credentials", "aws-key")),
    "realistic": (
        SeedSpec(".aws/credentials", "aws-key"),
        SeedSpec("config/openai.env", "openai-key"),
        SeedSpec("config/anthropic.env", "anthropic-key"),
        SeedSpec(".kube/config", "kubeconfig"),
        SeedSpec(".ssh/id_canary", "ssh-key"),
        SeedSpec(".env", "env"),
        SeedSpec("config/database.env", "database"),
        SeedSpec("finance/payroll.csv", "payroll"),
    ),
}


def _relative_parts(path: str) -> tuple[str, ...]:
    # Reject ambiguous spelling before pathlib normalizes it.
    if not path or path.startswith("/") or "\\" in path:
        raise UnsafePathError("artifact path must be a relative POSIX path")
    parts = path.split("/")
    if any(part in ("", ".", "..", ".agentcanary") for part in parts):
        raise UnsafePathError("artifact path contains traversal, empty or reserved components")
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise UnsafePathError("artifact path contains control characters")
    return PurePosixPath(path).parts


def _preflight(root_fd: int, parts: tuple[str, ...]) -> None:
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                return
            os.close(fd)
            fd = child
        try:
            os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise FileExistsError("artifact destination already exists")
    finally:
        os.close(fd)


@dataclass
class _CreatedFile:
    parent_fd: int
    name: str
    device: int
    inode: int


def seed(
    store: Store,
    root: str | Path,
    *,
    profile: str = "minimal",
    specs: Sequence[SeedSpec] | None = None,
    run_id: str | None = None,
) -> list[Canary]:
    """Write private files and commit all registrations together.

    No existing file is overwritten. Newly written files are removed on routine
    failure; abrupt termination can leave an unregistered artifact. Filesystem
    writes and SQLite commits cannot form a single cross-filesystem transaction.
    """
    if specs is None:
        if profile not in PROFILES:
            raise ValueError("unknown seed profile")
        specs = PROFILES[profile]
    if not specs or len(specs) > 1000:
        raise ValueError("seed batch must contain between 1 and 1000 artifacts")
    workspace = absolute_path(root)
    prepared = []
    paths: list[tuple[str, ...]] = []
    for spec in specs:
        parts = _relative_parts(spec.path)
        destination = workspace.joinpath(*parts)
        if destination == store.state_dir or store.state_dir in destination.parents:
            raise UnsafePathError("artifacts cannot be written into the state directory")
        for other in paths:
            if parts[: len(other)] == other or other[: len(parts)] == parts:
                raise UnsafePathError("seed destinations collide")
        paths.append(parts)
        prepared.append(generate(spec.kind, str(destination), template=spec.template))
    # Validate run labels before creating any artifact.
    from .models import Action, Event

    Event(action=Action.MONITOR_HEALTH, source="generator", run_id=run_id)
    root_fd = open_directory(workspace, create=True)
    created: list[_CreatedFile] = []
    directories: list[tuple[int, str]] = []
    committed = False
    try:
        for parts in paths:
            _preflight(root_fd, parts)
        for parts, artifact in zip(paths, prepared, strict=True):
            parent_fd = os.dup(root_fd)
            try:
                for part in parts[:-1]:
                    rollback_fd = os.dup(parent_fd)
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=parent_fd)
                    except FileExistsError:
                        os.close(rollback_fd)
                    except BaseException:
                        os.close(rollback_fd)
                        raise
                    else:
                        directories.append((rollback_fd, part))
                    child = os.open(
                        part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
                    )
                    os.close(parent_fd)
                    parent_fd = child
                # Reserve cleanup resources before creating the file. A dup()
                # failure after O_EXCL would otherwise leave an untracked file.
                rollback_fd = os.dup(parent_fd)
                try:
                    file_fd = os.open(
                        parts[-1],
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=parent_fd,
                    )
                except BaseException:
                    os.close(rollback_fd)
                    raise
                try:
                    info = os.fstat(file_fd)
                    created.append(_CreatedFile(rollback_fd, parts[-1], info.st_dev, info.st_ino))
                    os.fchmod(file_fd, 0o600)
                    with os.fdopen(file_fd, "wb", closefd=False) as stream:
                        stream.write(artifact.content.encode("utf-8"))
                        stream.flush()
                        os.fsync(file_fd)
                finally:
                    os.close(file_fd)
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        os.fsync(root_fd)
        result = [artifact.canary for artifact in prepared]
        store.register_many(result, run_id=run_id)
        committed = True
        return result
    finally:
        if not committed:
            for entry in reversed(created):
                # Disk errors can affect cleanup as well as writes. Continue
                # cleaning other entries, preserving the original failure.
                with suppress(OSError):
                    info = os.stat(entry.name, dir_fd=entry.parent_fd, follow_symlinks=False)
                    if (info.st_dev, info.st_ino) == (entry.device, entry.inode):
                        os.unlink(entry.name, dir_fd=entry.parent_fd)
                        os.fsync(entry.parent_fd)
            for fd, name in reversed(directories):
                with suppress(OSError):
                    os.rmdir(name, dir_fd=fd)
        for entry in created:
            with suppress(OSError):
                os.close(entry.parent_fd)
        for fd, _ in directories:
            with suppress(OSError):
                os.close(fd)
        with suppress(OSError):
            os.close(root_fd)


def create_canary(
    store: Store,
    root: str | Path,
    path: str,
    *,
    kind: str = "env",
    template: str | None = None,
    run_id: str | None = None,
) -> Canary:
    """Create a single registered artifact relative to the selected workspace."""
    return seed(store, root, specs=[SeedSpec(path, kind, template)], run_id=run_id)[0]
