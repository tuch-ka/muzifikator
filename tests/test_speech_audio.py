"""Тесты ffmpeg-обвязки: длительность, склейка, рык, отказы."""

import shutil
import subprocess

import pytest

from muzifikator.speech import AudioProcessingError, AudioTools

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")


def _tools() -> AudioTools:
    return AudioTools(ffmpeg_bin=str(FFMPEG), ffprobe_bin=str(FFPROBE))


def _silence(path, seconds: float) -> None:
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{seconds}",
            "-c:a",
            "libmp3lame",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_probe_duration(tmp_path):
    source = tmp_path / "a.mp3"
    _silence(source, 0.6)

    duration = _tools().probe_duration(source)

    assert 0.5 <= duration <= 0.75


def test_concat_durations_add_up(tmp_path):
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    target = tmp_path / "joined.mp3"
    _silence(first, 0.4)
    _silence(second, 0.4)

    tools = _tools()
    tools.concat([first, second], target)

    combined = tools.probe_duration(target)
    single = tools.probe_duration(first)
    assert combined == pytest.approx(single * 2, abs=0.15)


def test_concat_single_source_copies(tmp_path):
    source = tmp_path / "a.mp3"
    target = tmp_path / "copy.mp3"
    _silence(source, 0.2)

    _tools().concat([source], target)

    assert target.read_bytes() == source.read_bytes()


def test_growl_keeps_duration(tmp_path):
    source = tmp_path / "a.mp3"
    target = tmp_path / "growl.mp3"
    _silence(source, 1.0)

    tools = _tools()
    tools.growl(source, target)

    assert tools.probe_duration(target) == pytest.approx(1.0, abs=0.2)


def test_probe_fails_on_broken_file(tmp_path):
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"not audio")

    with pytest.raises(AudioProcessingError):
        _tools().probe_duration(broken)


def test_missing_binary_is_reported(tmp_path):
    tools = AudioTools(ffmpeg_bin="/nonexistent/ffmpeg", ffprobe_bin="/nonexistent/ffprobe")
    source = tmp_path / "a.mp3"
    source.write_bytes(b"x")

    with pytest.raises(AudioProcessingError, match="не найден"):
        tools.probe_duration(source)
