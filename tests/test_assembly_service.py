"""Тесты сервиса сборки: форматы, имена, атомарность, отказы."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from muzifikator.assembly import (
    AssemblyRequest,
    AssemblyService,
    EncodingError,
    InsufficientMusicError,
    UnknownFormatError,
)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")

FIXED_TIME = datetime(2026, 11, 26, 7, 25, 0)


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


@pytest.fixture
def inputs(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _tone(speech, frequency=440, seconds=3.0, sample_rate=24000)
    _tone(music, frequency=220, seconds=5.0, sample_rate=32000)
    return speech, music


def _service(tmp_path, **kwargs) -> AssemblyService:
    params = {
        "ffmpeg_bin": str(FFMPEG),
        "ffprobe_bin": str(FFPROBE),
        "output_dir": tmp_path / "out",
        "clock": lambda: FIXED_TIME,
    }
    params.update(kwargs)
    return AssemblyService(**params)


def _codec(path: Path) -> dict:
    result = subprocess.run(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["streams"][0]


def test_both_formats_by_default(tmp_path, inputs):
    speech, music = inputs
    result = _service(tmp_path).render(
        AssemblyRequest(speech=speech, music=music, text="Привет, мир!")
    )

    assert set(result.files) == {"mp3", "m4a"}
    assert result.formats == ("mp3", "m4a")
    assert result.duration_seconds == pytest.approx(5.0, abs=0.2)
    for path in result.files.values():
        assert path.is_file()
    assert _codec(result.files["mp3"])["codec_name"] == "mp3"
    assert _codec(result.files["m4a"])["codec_name"] == "aac"
    assert _codec(result.files["mp3"])["sample_rate"] == "44100"


def test_single_format(tmp_path, inputs):
    speech, music = inputs
    result = _service(tmp_path).render(
        AssemblyRequest(speech=speech, music=music, text="Привет", formats=("mp3",))
    )

    assert set(result.files) == {"mp3"}
    assert not list((tmp_path / "out").glob("*.m4a"))


def test_unknown_format_is_rejected_before_mix(tmp_path, inputs):
    speech, music = inputs

    with pytest.raises(UnknownFormatError):
        _service(tmp_path).render(
            AssemblyRequest(speech=speech, music=music, text="x", formats=("wav",))
        )

    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_name_uses_time_and_slug(tmp_path, inputs):
    speech, music = inputs
    result = _service(tmp_path).render(
        AssemblyRequest(speech=speech, music=music, text="Привет, мир!")
    )

    assert result.files["mp3"].name == "20261126-072500-privet-mir.mp3"


def test_second_render_in_same_second_gets_suffix(tmp_path, inputs):
    speech, music = inputs
    service = _service(tmp_path)

    first = service.render(AssemblyRequest(speech=speech, music=music, text="Привет"))
    second = service.render(AssemblyRequest(speech=speech, music=music, text="Привет"))

    assert first.files["mp3"].name == "20261126-072500-privet.mp3"
    assert second.files["mp3"].name == "20261126-072500-privet-2.mp3"
    assert first.files["mp3"].is_file()


def test_short_music_is_rejected(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _tone(speech, frequency=440, seconds=4.0, sample_rate=24000)
    _tone(music, frequency=220, seconds=4.0, sample_rate=32000)

    with pytest.raises(InsufficientMusicError):
        _service(tmp_path).render(AssemblyRequest(speech=speech, music=music, text="Привет"))

    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_failed_encoding_leaves_no_files(tmp_path, inputs):
    speech, music = inputs

    class BrokenService(AssemblyService):
        def _encode(self, master, encodings):
            encodings[0].path.write_bytes(b"partial")
            raise EncodingError("сломалось")

    service = BrokenService(
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
        output_dir=tmp_path / "out",
        clock=lambda: FIXED_TIME,
    )

    with pytest.raises(EncodingError):
        service.render(AssemblyRequest(speech=speech, music=music, text="Привет"))

    leftovers = list((tmp_path / "out").iterdir())
    assert leftovers == []
