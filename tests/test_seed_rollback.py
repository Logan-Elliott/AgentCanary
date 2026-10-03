"""Rollback remains best effort across resource and storage failures."""

import errno
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentcanary import SeedSpec, Store, seed
from agentcanary.filesystem import absolute_path


def test_absolute_root_spelling_matches_descriptor_root() -> None:
    assert absolute_path("//example/workspace") == absolute_path("/example/workspace")
    assert absolute_path("///example/workspace") == absolute_path("/example/workspace")
    assert absolute_path("//") == Path("/")


def test_persistent_fsync_failure_does_not_abort_batch_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "state")
    workspace = tmp_path / "workspace"
    real_fsync = os.fsync
    calls = 0

    def fail_persistently(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise OSError(errno.EIO, "simulated disk failure")
        real_fsync(fd)

    before = len(list(Path("/proc/self/fd").iterdir()))
    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail_persistently)
        with pytest.raises(OSError, match="simulated disk failure"):
            seed(store, workspace, specs=[SeedSpec("first", "env"), SeedSpec("second", "env")])
    assert list(workspace.iterdir()) == []
    assert store.canaries() == []
    assert len(list(Path("/proc/self/fd").iterdir())) == before


def test_descriptor_limit_failure_leaves_no_unregistered_artifacts(tmp_path: Path) -> None:
    # A child owns the resource limit; the test runner's limit remains unchanged.
    program = """
import errno
import resource
import sys
from pathlib import Path
from agentcanary import SeedSpec, Store, seed

root = Path(sys.argv[1])
store = Store(root / 'state')
workspace = root / 'workspace'
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (min(64, hard), hard))
try:
    seed(store, workspace, specs=[SeedSpec(f'item-{n}', 'env') for n in range(80)])
except OSError as exc:
    assert exc.errno == errno.EMFILE
else:
    raise AssertionError('the finite descriptor limit was not exercised')
finally:
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
assert list(workspace.iterdir()) == []
assert store.canaries() == []
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
