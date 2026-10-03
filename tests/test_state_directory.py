"""State operations must not silently mutate an operator's existing directory."""

import stat
from pathlib import Path

import pytest

from agentcanary import Store
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
