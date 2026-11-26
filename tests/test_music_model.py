"""Тест реальной модели MusicGen: запускается только через `-m model`."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from muzifikator.music import MusicGenProvider, MusicRequest, MusicService, TransformersBackend

pytestmark = [
    pytest.mark.model,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
        reason="нужны ffmpeg и ffprobe",
    ),
]


def _backend() -> TransformersBackend:
    # Общий каталог весов: иначе каждый прогон скачивает ~2 ГБ заново.
    return TransformersBackend("facebook/musicgen-small", models_dir=Path("models"), device="auto")


def test_same_seed_gives_same_audio():
    backend = _backend()

    first = backend.generate(prompt="folk metal", seconds=1.0, seed=42)
    second = backend.generate(prompt="folk metal", seconds=1.0, seed=42)

    assert np.array_equal(first, second)


def test_service_generates_track_longer_than_request(tmp_path):
    backend = _backend()
    service = MusicService(
        MusicGenProvider(backend),
        ffmpeg_bin=str(shutil.which("ffmpeg")),
        ffprobe_bin=str(shutil.which("ffprobe")),
        default_prompt="folk metal",
        model_name=backend.model_name,
    )

    result = service.generate(MusicRequest(duration_seconds=2, seed=7), tmp_path / "work")

    assert result.path.is_file()
    assert result.duration_seconds >= 2
    assert result.seed == 7
    assert result.segments == 1
