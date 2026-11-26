"""Тесты минимальной длительности трека."""

import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from muzifikator.assembly import AssemblyRequest, AssemblyService, InsufficientMusicError
from muzifikator.config import Settings

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")


def test_default_setting():
    assert Settings().music_min_duration_seconds == pytest.approx(20.0)


def test_setting_from_environment(monkeypatch):
    monkeypatch.setenv("MUSIC_MIN_DURATION_SECONDS", "15")

    assert Settings().music_min_duration_seconds == pytest.approx(15.0)


@pytest.mark.parametrize("value", ["0", "-5"])
def test_non_positive_setting_rejected(monkeypatch, value):
    monkeypatch.setenv("MUSIC_MIN_DURATION_SECONDS", value)

    with pytest.raises(ValidationError):
        Settings()


def _tone(path: Path, *, frequency: int, seconds: float, sample_rate: int) -> None:
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate={sample_rate}:duration={seconds}",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _service(tmp_path, *, minimum: float) -> AssemblyService:
    return AssemblyService(
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
        output_dir=tmp_path / "out",
        formats=("mp3",),
        min_duration_seconds=minimum,
    )


def test_short_speech_gets_minimum_length(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _tone(speech, frequency=440, seconds=1.0, sample_rate=24000)
    _tone(music, frequency=220, seconds=5.0, sample_rate=32000)

    result = _service(tmp_path, minimum=5.0).render(
        AssemblyRequest(speech=speech, music=music, text="Коротко")
    )

    assert result.duration_seconds == pytest.approx(5.0, abs=0.2)


def test_long_speech_keeps_speech_plus_tail(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _tone(speech, frequency=440, seconds=6.0, sample_rate=24000)
    _tone(music, frequency=220, seconds=8.5, sample_rate=32000)

    result = _service(tmp_path, minimum=5.0).render(
        AssemblyRequest(speech=speech, music=music, text="Длинно")
    )

    assert result.duration_seconds == pytest.approx(8.0, abs=0.2)


def test_music_below_minimum_is_rejected(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _tone(speech, frequency=440, seconds=1.0, sample_rate=24000)
    _tone(music, frequency=220, seconds=3.0, sample_rate=32000)

    with pytest.raises(InsufficientMusicError):
        _service(tmp_path, minimum=5.0).render(
            AssemblyRequest(speech=speech, music=music, text="Мало музыки")
        )


def test_required_music_duration_helper(tmp_path):
    service = _service(tmp_path, minimum=20.0)

    assert service.required_music_duration(1.0) == pytest.approx(20.0)
    assert service.required_music_duration(30.0) == pytest.approx(32.0)
