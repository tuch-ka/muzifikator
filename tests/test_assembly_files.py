"""Тесты имён файлов, транслитерации и атомарных операций."""

from datetime import datetime

import pytest

from muzifikator.assembly.files import (
    TEMP_PREFIX,
    build_stem,
    cleanup,
    plan_output_files,
    replace_all,
    slugify,
    temporary_path,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Привет, мир!", "privet-mir"),
        ("Ёлка", "elka"),
        ("Щука", "shchuka"),
        ("Съешь ещё этих булок", "sesh-eshche-etikh-bulok"),
        ("Hello, World", "hello-world"),
        ("123", "123"),
        ("!!!", "audio"),
        ("", "audio"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slug_is_limited():
    assert len(slugify("слово " * 20)) <= 40


def test_build_stem_uses_time_and_slug():
    stem = build_stem("Привет, мир!", now=datetime(2026, 11, 26, 7, 25, 0))

    assert stem == "20261126-072500-privet-mir"


def test_plan_output_files_uses_all_formats(tmp_path):
    planned = plan_output_files(
        tmp_path,
        text="Привет",
        formats=("mp3", "m4a"),
        now=datetime(2026, 11, 26, 7, 25, 0),
    )

    assert planned == {
        "mp3": tmp_path / "20261126-072500-privet.mp3",
        "m4a": tmp_path / "20261126-072500-privet.m4a",
    }


def test_plan_output_files_avoids_collision(tmp_path):
    (tmp_path / "20261126-072500-privet.mp3").write_bytes(b"old")

    planned = plan_output_files(
        tmp_path,
        text="Привет",
        formats=("mp3", "m4a"),
        now=datetime(2026, 11, 26, 7, 25, 0),
    )

    assert planned["mp3"].name == "20261126-072500-privet-2.mp3"
    assert planned["m4a"].name == "20261126-072500-privet-2.m4a"


def test_temporary_path_is_hidden_and_cleanable(tmp_path):
    path = temporary_path(tmp_path, ".mp3")

    assert path.name.startswith(TEMP_PREFIX)
    cleanup([path])
    assert not path.exists()
    cleanup([path])


def test_replace_all_cleans_up_on_failure(tmp_path):
    source = tmp_path / ".tmp-a"
    source.write_bytes(b"a")
    missing = tmp_path / ".tmp-missing"
    target = tmp_path / "out.mp3"

    with pytest.raises(OSError):
        replace_all([(source, target), (missing, tmp_path / "out2.mp3")])

    assert not target.exists()
