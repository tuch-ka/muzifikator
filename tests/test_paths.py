"""Тесты проверки путей внутри корня."""

import os

import pytest

from muzifikator.paths import PathOutsideRootError, resolve_within


def test_empty_is_root(tmp_path):
    assert resolve_within(tmp_path, "") == tmp_path.resolve()


def test_nested_path(tmp_path):
    resolved = resolve_within(tmp_path, "a/b")

    assert resolved == (tmp_path / "a" / "b").resolve()


def test_dot_segments_inside_are_allowed(tmp_path):
    (tmp_path / "a").mkdir()

    assert resolve_within(tmp_path, "a/../a") == (tmp_path / "a").resolve()


@pytest.mark.parametrize("raw", ["..", "../x", "a/../../x"])
def test_traversal_is_rejected(tmp_path, raw):
    with pytest.raises(PathOutsideRootError):
        resolve_within(tmp_path, raw)


def test_absolute_path_is_rejected(tmp_path):
    with pytest.raises(PathOutsideRootError):
        resolve_within(tmp_path, "/etc")


def test_null_byte_is_rejected(tmp_path):
    with pytest.raises(PathOutsideRootError):
        resolve_within(tmp_path, "a\x00b")


def test_symlink_outside_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    os.symlink(outside, tmp_path / "link")

    with pytest.raises(PathOutsideRootError):
        resolve_within(tmp_path, "link")


def test_symlink_inside_is_allowed(tmp_path):
    (tmp_path / "real").mkdir()
    os.symlink(tmp_path / "real", tmp_path / "link")

    assert resolve_within(tmp_path, "link") == (tmp_path / "real").resolve()
