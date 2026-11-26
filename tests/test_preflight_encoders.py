"""Тесты проверки энкодеров ffmpeg в preflight."""

import stat

import pytest

from muzifikator import preflight
from muzifikator.config import Settings


def _write_script(directory, name: str, body: str):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _ffmpeg(directory, *, encoders=("libmp3lame", "aac"), encoders_exit: int = 0):
    lines = "".join(f'  printf " A....D {encoder}  codec\\n"\n' for encoder in encoders)
    body = (
        'case "$*" in\n'
        "  *-encoders*)\n"
        f"{lines}"
        f"    exit {encoders_exit}\n"
        "    ;;\n"
        "  *)\n"
        '    echo "ffmpeg version 9.1 Copyright"\n'
        "    ;;\n"
        "esac\n"
    )
    return _write_script(directory, "ffmpeg", body)


def _ffprobe(directory):
    return _write_script(directory, "ffprobe", 'echo "ffprobe version 9.1"\n')


def test_both_encoders_present(tmp_path):
    result = preflight.run_preflight(
        Settings(ffmpeg_bin=_ffmpeg(tmp_path), ffprobe_bin=_ffprobe(tmp_path))
    )

    assert result.ok
    assert result.ffmpeg.missing_encoders == ()
    assert result.ffmpeg.error is None


def test_missing_aac_blocks_startup(tmp_path):
    result = preflight.run_preflight(
        Settings(
            ffmpeg_bin=_ffmpeg(tmp_path, encoders=("libmp3lame",)),
            ffprobe_bin=_ffprobe(tmp_path),
        )
    )

    assert not result.ok
    assert result.ffmpeg.missing_encoders == ("aac",)
    assert "aac" in preflight.format_failure(result)


def test_missing_mp3_encoder_is_reported(tmp_path):
    result = preflight.run_preflight(
        Settings(
            ffmpeg_bin=_ffmpeg(tmp_path, encoders=("aac",)),
            ffprobe_bin=_ffprobe(tmp_path),
        )
    )

    assert result.ffmpeg.missing_encoders == ("libmp3lame",)


def test_audio_toolbox_aac_does_not_count_as_aac(tmp_path):
    result = preflight.run_preflight(
        Settings(
            ffmpeg_bin=_ffmpeg(tmp_path, encoders=("libmp3lame", "aac_at")),
            ffprobe_bin=_ffprobe(tmp_path),
        )
    )

    assert not result.ok
    assert result.ffmpeg.missing_encoders == ("aac",)


def test_encoders_failure_is_reported(tmp_path):
    result = preflight.run_preflight(
        Settings(
            ffmpeg_bin=_ffmpeg(tmp_path, encoders_exit=1),
            ffprobe_bin=_ffprobe(tmp_path),
        )
    )

    assert not result.ok
    assert result.ffmpeg.error is not None
    assert "энкодеров" in result.ffmpeg.error


def test_real_ffmpeg_has_required_encoders():
    result = preflight.run_preflight(Settings())

    if not result.ffmpeg.available:
        pytest.skip("ffmpeg не установлен")
    assert result.ffmpeg.missing_encoders == ()
