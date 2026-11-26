"""Контракты слоя музыки: запросы, результаты, провайдер, бэкенд, ошибки."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

MIN_DURATION_SECONDS = 1.0
WINDOW_SECONDS = 30.0
CROSSFADE_SECONDS = 2.0
MODEL_SAMPLE_RATE = 32000


class MusicError(RuntimeError):
    """Базовая ошибка слоя музыки."""


class MusicRequestError(MusicError):
    """Запрос музыки некорректен."""


class MusicModelError(MusicError):
    """Модель не загружается."""


class MusicGenerationError(MusicError):
    """Сегмент не сгенерирован."""


class MusicResourceError(MusicError):
    """Не хватило памяти или недоступно устройство вычислений."""


@dataclass(frozen=True)
class MusicRequest:
    duration_seconds: float
    prompt: str | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds < MIN_DURATION_SECONDS:
            raise MusicRequestError(
                f"длительность должна быть не меньше {MIN_DURATION_SECONDS:g} с"
            )
        if self.seed is not None and self.seed < 0:
            raise MusicRequestError("seed не может быть отрицательным")


@dataclass(frozen=True)
class MusicResult:
    path: Path
    duration_seconds: float
    seed: int
    prompt: str
    model: str
    segments: int


@runtime_checkable
class MusicBackend(Protocol):
    """Генератор одного сегмента: модель за протоколом."""

    model_name: str

    def load(self) -> None:
        """Загрузить модель и процессор, если ещё не загружены."""
        ...

    def generate(self, *, prompt: str, seconds: float, seed: int) -> NDArray[np.float32]:
        """Аудио сегмента: моно, float, 32 кГц."""
        ...


@runtime_checkable
class MusicProvider(Protocol):
    name: str

    def segment(self, *, prompt: str, seconds: float, seed: int, target: Path) -> None:
        """Сгенерировать сегмент и записать WAV в target."""
        ...
