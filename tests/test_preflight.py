"""Тесты preflight на подставных бинарях."""

import stat

import pytest

from muzifikator import preflight
from muzifikator.config import Settings


def _write_binary(directory, name: str, body: str):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _write_ffmpeg(
    directory,
    name: str = "ffmpeg",
    *,
    version_line: str = "ffmpeg version 7.1 Copyright",
    encoders: tuple[str, ...] = ("libmp3lame", "aac"),
):
    encoders_body = "".join(f'  printf " A....D {encoder}  codec\\n"\n' for encoder in encoders)
    body = (
        'case "$*" in\n'
        "  *-encoders*)\n"
        f"{encoders_body}"
        "    ;;\n"
        "  *)\n"
        f'    echo "{version_line}"\n'
        "    ;;\n"
        "esac\n"
    )
    return _write_binary(directory, name, body)


@pytest.fixture
def fake_bins(tmp_path):
    ffmpeg = _write_ffmpeg(tmp_path)
    ffprobe = _write_binary(tmp_path, "ffprobe", 'echo "ffprobe version 7.1 Copyright"\n')
    return ffmpeg, ffprobe


def test_both_binaries_available(fake_bins):
    ffmpeg, ffprobe = fake_bins
    result = preflight.run_preflight(Settings(ffmpeg_bin=ffmpeg, ffprobe_bin=ffprobe))

    assert result.ok
    assert result.ffmpeg.version == "7.1"
    assert result.ffprobe.version == "7.1"
    assert result.ffmpeg.path == str(ffmpeg)


def test_nonzero_exit_is_reported(tmp_path, fake_bins):
    _, ffprobe = fake_bins
    broken = _write_binary(tmp_path, "broken", 'echo "cannot load" >&2\nexit 3\n')
    result = preflight.run_preflight(Settings(ffmpeg_bin=broken, ffprobe_bin=ffprobe))

    assert not result.ok
    assert result.ffmpeg.available is False
    assert "код возврата 3" in result.ffmpeg.error
    assert "cannot load" in result.ffmpeg.error


def test_timeout_is_reported(tmp_path, fake_bins, monkeypatch):
    _, ffprobe = fake_bins
    slow = _write_binary(tmp_path, "slow", "sleep 5\n")
    monkeypatch.setattr(preflight, "VERSION_TIMEOUT_SECONDS", 0.2)

    result = preflight.run_preflight(Settings(ffmpeg_bin=slow, ffprobe_bin=ffprobe))

    assert not result.ok
    assert "таймаут" in result.ffmpeg.error


def test_missing_configured_path_is_reported(tmp_path, fake_bins):
    _, ffprobe = fake_bins
    absent = tmp_path / "absent-ffmpeg"
    result = preflight.run_preflight(Settings(ffmpeg_bin=absent, ffprobe_bin=ffprobe))

    assert not result.ok
    assert result.ffmpeg.path == str(absent)
    assert "путь из настроек не найден" in result.ffmpeg.error


def test_binary_not_in_path_and_not_configured(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: None)

    result = preflight.run_preflight(Settings())

    assert not result.ok
    assert result.ffmpeg.error == "не найден в PATH, а FFMPEG_BIN не задан"
    assert result.ffprobe.error == "не найден в PATH, а FFPROBE_BIN не задан"


def test_version_unknown_keeps_binary_available(fake_bins):
    ffmpeg, _ = fake_bins
    odd = _write_ffmpeg(ffmpeg.parent, "odd", version_line="no version line here")
    result = preflight.run_preflight(Settings(ffmpeg_bin=odd, ffprobe_bin=ffmpeg))

    assert result.ok
    assert result.ffmpeg.version is None


def test_failure_message_lists_problems_and_hints(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: None)
    result = preflight.run_preflight(Settings())
    message = preflight.format_failure(result)

    assert "ffmpeg:" in message
    assert "ffprobe:" in message
    assert "brew install ffmpeg" in message
    assert "apt install ffmpeg" in message
    assert "dnf install ffmpeg" in message
    assert "FFMPEG_BIN" in message
    assert "FFPROBE_BIN" in message
