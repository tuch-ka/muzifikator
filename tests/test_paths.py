"""Тесты правил путей."""

import pytest

from muzifikator.paths import (
    StorageDirError,
    expand,
    home_root,
    is_inside,
    project_root,
    storage_dir,
)


def test_project_root_has_alembic_ini():
    assert (project_root() / "alembic.ini").is_file()


def test_expand_home():
    assert expand("~") == home_root()


def test_expand_relative_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert expand("data") == tmp_path / "data"


def test_is_inside(tmp_path):
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)

    assert is_inside(child, tmp_path)
    assert is_inside(tmp_path, tmp_path)
    assert not is_inside(tmp_path.parent, tmp_path)


def test_storage_dir_accepts_existing_directory(tmp_path):
    target = tmp_path / "out"
    target.mkdir()

    assert storage_dir(str(target)) == target.resolve()


def test_storage_dir_expands_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "out"
    target.mkdir()

    assert storage_dir("~/out") == target.resolve()


@pytest.mark.parametrize("raw", ["", "out", "./out"])
def test_storage_dir_rejects_relative(tmp_path, raw):
    with pytest.raises(StorageDirError):
        storage_dir(raw)


def test_storage_dir_rejects_missing(tmp_path):
    with pytest.raises(StorageDirError):
        storage_dir(str(tmp_path / "nope"))


def test_storage_dir_rejects_file(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("x", encoding="utf-8")

    with pytest.raises(StorageDirError):
        storage_dir(str(path))


def test_storage_dir_rejects_unwritable(tmp_path):
    target = tmp_path / "locked"
    target.mkdir()
    target.chmod(0o500)
    try:
        with pytest.raises(StorageDirError):
            storage_dir(str(target))
    finally:
        target.chmod(0o700)


def test_storage_dir_allows_repository_path(tmp_path):
    # Проверка «вне репозитория» намеренно отсутствует.
    target = tmp_path / "inside"
    target.mkdir()

    assert storage_dir(str(target)) == target.resolve()
    assert not is_inside(target, project_root())
