"""Тесты микса: длительность, дакинг, фейды, громкость."""

import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from muzifikator.assembly.base import InsufficientMusicError
from muzifikator.assembly.mix import Mixer
from muzifikator.media import MediaTools

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")

SAMPLE_RATE = 44100


def _tone(path: Path, *, frequency: int, seconds: float, sample_rate: int, volume: float):
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate={sample_rate}:duration={seconds}",
            "-af",
            f"volume={volume}",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _media() -> MediaTools:
    return MediaTools(ffmpeg_bin=str(FFMPEG), ffprobe_bin=str(FFPROBE))


def _load(path: Path) -> np.ndarray:
    with wave.open(str(path)) as handle:
        assert handle.getframerate() == SAMPLE_RATE
        data = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def _tone_amplitude(samples: np.ndarray, frequency: int, start: float, length: float) -> float:
    begin = int(start * SAMPLE_RATE)
    end = int((start + length) * SAMPLE_RATE)
    segment = samples[begin:end]
    windowed = segment * np.hanning(len(segment))
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(segment), 1 / SAMPLE_RATE)
    index = int(np.argmin(np.abs(freqs - frequency)))
    return float(spectrum[index]) / len(segment) * 2


def _rms(samples: np.ndarray, start: float, length: float) -> float:
    begin = int(start * SAMPLE_RATE)
    end = int((start + length) * SAMPLE_RATE)
    return float(np.sqrt(np.mean(samples[begin:end] ** 2)))


@pytest.fixture
def mixed(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    target = tmp_path / "mixed.wav"
    _tone(speech, frequency=440, seconds=3.0, sample_rate=24000, volume=0.5)
    _tone(music, frequency=220, seconds=5.0, sample_rate=32000, volume=0.3)

    media = _media()
    Mixer(media).mix(
        speech,
        music,
        target,
        speech_duration=3.0,
        music_duration=5.0,
    )
    return target, media


def test_mix_duration_is_speech_plus_tail(mixed):
    target, media = mixed

    assert media.probe_duration(target) == pytest.approx(5.0, abs=0.15)


def test_music_is_ducked_under_speech(mixed):
    target, _ = mixed
    samples = _load(target)

    under_speech = _tone_amplitude(samples, 220, start=1.0, length=1.0)
    in_tail = _tone_amplitude(samples, 220, start=3.2, length=1.0)

    assert in_tail > under_speech * 1.5


def test_speech_dominates_under_ducking(mixed):
    target, _ = mixed
    samples = _load(target)

    speech_level = _tone_amplitude(samples, 440, start=1.0, length=1.0)
    music_level = _tone_amplitude(samples, 220, start=1.0, length=1.0)

    assert speech_level > music_level * 2


def test_music_fades_lower_the_edges(tmp_path):
    speech = tmp_path / "silence.wav"
    music = tmp_path / "music.wav"
    target = tmp_path / "mixed.wav"
    subprocess.run(
        [
            str(FFMPEG),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            "3",
            "-c:a",
            "pcm_s16le",
            str(speech),
        ],
        check=True,
        capture_output=True,
    )
    _tone(music, frequency=220, seconds=5.0, sample_rate=32000, volume=0.3)

    Mixer(_media()).mix(speech, music, target, speech_duration=3.0, music_duration=5.0)

    samples = _load(target)
    middle = _rms(samples, start=2.2, length=0.6)
    assert _rms(samples, start=0.0, length=0.2) < middle * 0.5
    assert _rms(samples, start=4.8, length=0.2) < middle * 0.5


def test_loudness_and_peak(mixed):
    target, _ = mixed
    result = subprocess.run(
        [
            str(FFMPEG),
            "-hide_banner",
            "-nostats",
            "-i",
            str(target),
            "-af",
            "ebur128",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    integrated = [
        float(line.split("I:")[1].split()[0])
        for line in result.stderr.splitlines()
        if "I:" in line and "LUFS" in line
    ]

    assert integrated
    assert integrated[-1] == pytest.approx(-16.0, abs=1.5)
    peak = float(np.max(np.abs(_load(target))))
    assert peak <= 0.9


def test_short_music_is_rejected(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _tone(speech, frequency=440, seconds=3.0, sample_rate=24000, volume=0.5)
    _tone(music, frequency=220, seconds=3.5, sample_rate=32000, volume=0.3)

    with pytest.raises(InsufficientMusicError):
        Mixer(_media()).mix(
            speech,
            music,
            tmp_path / "out.wav",
            speech_duration=3.0,
            music_duration=3.5,
        )
