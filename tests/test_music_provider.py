"""Тесты провайдера музыки на фейковом бэкенде (модель не грузится)."""

import shutil
import subprocess

import numpy as np
import pytest

from muzifikator.music import (
    MusicGenerationError,
    MusicGenProvider,
    MusicResourceError,
    write_wav,
)

FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFPROBE is None, reason="нужен ffprobe")


def _duration(path) -> float:
    output = subprocess.run(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(output.stdout.strip())


class FakeBackend:
    model_name = "fake-model"

    def __init__(self, fail: Exception | None = None) -> None:
        self.loads = 0
        self.calls: list[tuple[str, float, int]] = []
        self.fail = fail

    def load(self) -> None:
        self.loads += 1

    def generate(self, *, prompt, seconds, seed):
        self.calls.append((prompt, seconds, seed))
        self.load()
        if self.fail is not None:
            raise self.fail
        samples = int(32000 * seconds)
        return np.zeros(samples, dtype=np.float32)


def test_segment_writes_valid_wav(tmp_path):
    backend = FakeBackend()
    provider = MusicGenProvider(backend)
    target = tmp_path / "segment.wav"

    provider.segment(prompt="folk metal", seconds=1.5, seed=7, target=target)

    assert target.is_file()
    assert _duration(target) == pytest.approx(1.5, abs=0.05)
    assert backend.calls == [("folk metal", 1.5, 7)]


def test_seed_and_prompt_are_passed_through(tmp_path):
    backend = FakeBackend()
    provider = MusicGenProvider(backend)

    provider.segment(prompt="symphonic metal", seconds=1.0, seed=11, target=tmp_path / "a.wav")
    provider.segment(prompt="symphonic metal", seconds=1.0, seed=12, target=tmp_path / "b.wav")

    assert [call[2] for call in backend.calls] == [11, 12]
    assert backend.loads == 2


def test_backend_failure_leaves_no_target(tmp_path):
    backend = FakeBackend(fail=MusicResourceError("не хватило памяти"))
    provider = MusicGenProvider(backend)
    target = tmp_path / "segment.wav"

    with pytest.raises(MusicResourceError):
        provider.segment(prompt="folk metal", seconds=1.0, seed=1, target=target)

    assert not target.exists()
    assert not list(tmp_path.glob("*.part.wav"))


def test_write_wav_clips_out_of_range(tmp_path):
    path = tmp_path / "clipped.wav"

    write_wav(path, np.array([-2.0, 0.0, 2.0], dtype=np.float32), 32000)

    assert path.is_file()
    assert _duration(path) == pytest.approx(3 / 32000, abs=0.01)


def test_generation_error_type_preserved(tmp_path):
    backend = FakeBackend(fail=MusicGenerationError("сбой модели"))
    provider = MusicGenProvider(backend)

    with pytest.raises(MusicGenerationError, match="сбой модели"):
        provider.segment(prompt="folk", seconds=1.0, seed=1, target=tmp_path / "x.wav")

    assert not (tmp_path / "x.wav").exists()
