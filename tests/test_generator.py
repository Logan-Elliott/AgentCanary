import hashlib
from pathlib import Path

import pytest

from agentcanary import Store, StoreError
from agentcanary.filesystem import UnsafePathError
from agentcanary.generator import SeedSpec, create_canary, seed
from agentcanary.models import TOKEN_PATTERN
from agentcanary.templates import BUILTINS, LABEL, generate


@pytest.mark.parametrize("kind", BUILTINS)
def test_all_types_are_unique_synthetic_and_correlatable(kind: str) -> None:
    first = generate(kind, "/workspace/file")
    second = generate(kind, "/workspace/file")
    assert first.canary.id != second.canary.id
    assert first.canary.token != second.canary.token
    assert TOKEN_PATTERN.fullmatch(first.canary.token)
    assert first.canary.token in first.content
    assert LABEL in first.content
    assert first.canary.sha256 == hashlib.sha256(first.content.encode()).hexdigest()
    assert "BEGIN OPENSSH PRIVATE KEY" not in first.content
    assert "sk-ant-" not in first.content
    assert "AKIA" not in first.content


def test_custom_templates_are_inert_and_labelled() -> None:
    artifact = generate("custom", "/file", template="literal $$(command) ${token} $canary_id")
    assert "$(command)" in artifact.content
    assert LABEL in artifact.content
    for text in ("no marker", "$unknown $token", "${token", "\x00$token", "$token" + "x" * 262144):
        with pytest.raises(ValueError):
            generate("custom", "/file", template=text)


def test_seed_writes_private_files_and_atomic_events(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    records = seed(store, tmp_path / "workspace", profile="realistic", run_id="demo")
    assert len(records) == 8
    assert len(store.events(run_id="demo")) == 8
    for record in records:
        path = Path(record.path)
        assert record.token in path.read_text()
        assert path.stat().st_mode & 0o777 == 0o600
        assert store.get_canary(record.id) == record
    with pytest.raises(FileExistsError):
        seed(store, tmp_path / "workspace", profile="realistic")
    assert len(store.canaries()) == 8


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "a/../b",
        "./file",
        "a//b",
        ".agentcanary/file",
        "a/",
        "",
        "a\\b",
        "line\nbreak",
    ],
)
def test_bad_destinations_rejected(tmp_path: Path, path: str) -> None:
    store = Store(tmp_path / "state")
    with pytest.raises(UnsafePathError):
        create_canary(store, tmp_path / "workspace", path)
    assert not store.canaries()


def test_preflight_preserves_existing_files_and_rejects_links(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "taken").write_text("existing")
    with pytest.raises(FileExistsError):
        seed(store, workspace, specs=[SeedSpec("new", "env"), SeedSpec("taken", "env")])
    assert not (workspace / "new").exists()
    assert (workspace / "taken").read_text() == "existing"
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        create_canary(store, workspace, "link/file")
    (workspace / "dangling").symlink_to(outside / "missing")
    with pytest.raises(FileExistsError):
        create_canary(store, workspace, "dangling")
    with pytest.raises(UnsafePathError):
        create_canary(store, tmp_path, "state/file")
    assert not list(outside.iterdir())
    assert not store.canaries()


def test_batch_collision_and_store_failure_roll_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "state")
    workspace = tmp_path / "workspace"
    with pytest.raises(UnsafePathError):
        seed(store, workspace, specs=[SeedSpec("a", "env"), SeedSpec("a/file", "env")])

    def fail(*args: object, **kwargs: object) -> None:
        raise StoreError("simulated database failure")

    monkeypatch.setattr(store, "register_many", fail)
    with pytest.raises(StoreError):
        seed(store, workspace, profile="realistic")
    assert list(workspace.iterdir()) == []
    assert not store.canaries()


def test_readonly_workspace_fails_without_registration(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o500)
    try:
        with pytest.raises(PermissionError):
            create_canary(store, workspace, "file")
        assert not store.canaries()
    finally:
        workspace.chmod(0o700)
