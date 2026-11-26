"""Провайдер музыки: сегмент модели → WAV-файл."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .base import MODEL_SAMPLE_RATE, MusicBackend, MusicGenerationError


class MusicGenProvider:
    """Пишет сегменты в WAV; модель скрыта за бэкендом."""

    name = "musicgen"

    def __init__(self, backend: MusicBackend, *, sample_rate: int = MODEL_SAMPLE_RATE) -> None:
        self.backend = backend
        self.sample_rate = sample_rate

    def segment(self, *, prompt: str, seconds: float, seed: int, target: Path) -> None:
        audio = self.backend.generate(prompt=prompt, seconds=seconds, seed=seed)
        part = target.with_suffix(".part.wav")
        try:
            write_wav(part, audio, self.sample_rate)
            part.replace(target)
        except Exception as exc:
            part.unlink(missing_ok=True)
            if isinstance(exc, (MusicGenerationError, OSError, ValueError)):
                raise MusicGenerationError(f"не удалось записать сегмент {target}: {exc}") from exc
            raise


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    """PCM 16 бит, моно. Значения вне [-1, 1] обрезаются."""
    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
