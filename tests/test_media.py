"""Тесты общего ffmpeg-слоя: кроссфейд, склейка, длительность."""

import shutil
import subprocess

import pytest

from muzifikator.media import MediaError, MediaTools

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")


def _tools() -> MediaTools:
    return MediaTools(ffmpeg_bin=str(FFMPEG), ffprobe_bin=str(FFPROBE))


def _tone(path, seconds: float, frequency: int = 440) -> None:
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=32000:duration={seconds}",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_crossfade_two_segments(tmp_path):
    first = tmp_path / "a.wav"
    second = tmp_path / "b.wav"
    target = tmp_path / "joined.wav"
    _tone(first, 3.0)
    _tone(second, 3.0, frequency=660)

    tools = _tools()
    tools.crossfade_concat([first, second], target, crossfade_seconds=1.0)

    assert tools.probe_duration(target) == pytest.approx(5.0, abs=0.15)


def test_crossfade_three_segments(tmp_path):
    sources = []
    for index in range(3):
        source = tmp_path / f"part-{index}.wav"
        _tone(source, 3.0, frequency=440 + index * 110)
        sources.append(source)
    target = tmp_path / "joined.wav"

    tools = _tools()
    tools.crossfade_concat(sources, target, crossfade_seconds=1.0)

    assert tools.probe_duration(target) == pytest.approx(7.0, abs=0.2)


def test_crossfade_single_segment_copies(tmp_path):
    source = tmp_path / "a.wav"
    target = tmp_path / "copy.wav"
    _tone(source, 1.0)

    _tools().crossfade_concat([source], target)

    assert target.read_bytes() == source.read_bytes()


def test_crossfade_empty_list_is_error(tmp_path):
    with pytest.raises(MediaError):
        _tools().crossfade_concat([], tmp_path / "x.wav")
