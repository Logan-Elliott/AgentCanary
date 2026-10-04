"""Directory-descriptor operations: never follow a selected path's symlinks."""

from __future__ import annotations

import os
import stat
from contextlib import suppress
from pathlib import Path


class UnsafePathError(ValueError):
    """A path violates the local filesystem safety contract."""


def absolute_path(path: str | Path) -> Path:
    value = Path(path)
    if ".." in value.parts:
        raise UnsafePathError("parent traversal is not allowed")
    # POSIX permits a distinct // anchor; our descriptor traversal starts at /.
    # Keep lexical containment checks consistent with that traversal.
    return Path("/" + os.path.abspath(value).lstrip("/"))


def open_directory(path: str | Path, *, create: bool = False, private: bool = False) -> int:
    """Open each component without following links; caller owns the returned fd."""
    absolute = absolute_path(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in absolute.parts[1:]:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=fd)
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd
            )
            os.close(fd)
            fd = child
        if private:
            info = os.fstat(fd)
            if info.st_uid != os.getuid():
                raise UnsafePathError("state directory must belong to the current user")
            if absolute == Path("/"):
                raise UnsafePathError("state directory cannot be the filesystem root")
            if stat.S_IMODE(info.st_mode) & 0o077:
                raise UnsafePathError("state directory must be private (mode 0700)")
        return fd
    except BaseException:
        os.close(fd)
        raise


def check_private_file(directory_fd: int, name: str, *, missing_ok: bool = False) -> None:
    # SQLite removes sidecars when its last connection closes. stat() can have
    # resolved the old inode just before unlink and report a zero link count.
    # Recheck only these optional names; a primary DB or arbitrary file must
    # never gain a disappearing-file exception from this sidecar-specific race.
    optional_sidecar = missing_ok and name in (
        "events.sqlite3-wal",
        "events.sqlite3-shm",
        "events.sqlite3-journal",
    )
    for _ in range(3):
        try:
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            if missing_ok:
                return
            raise
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink > 1:
            raise UnsafePathError(
                "state files must be regular, singly linked and owned by this user"
            )
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise UnsafePathError("state files must be private (mode 0600)")
        if info.st_nlink == 1:
            return
        if info.st_nlink != 0 or not optional_sidecar:
            break
    raise UnsafePathError("state files must be regular, singly linked and owned by this user")
