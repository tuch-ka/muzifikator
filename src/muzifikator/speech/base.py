"""Контракты слоя речи: запросы, результаты, провайдер, ошибки."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

MIN_RATE_PERCENT = -100
MAX_RATE_PERCENT = 200
MIN_PITCH_HZ = -100
MAX_PITCH_HZ = 100


class SpeechError(RuntimeError):
    """Базовая ошибка слоя речи."""


class SynthesisError(SpeechError):
    """Провайдер не смог синтезировать речь."""


class EmptyTextError(SynthesisError):
    """Синтез запрошен для пустого текста."""


class VoiceListError(SpeechError):
    """Список голосов получить не удалось."""


class UnknownVoiceError(SpeechError):
    """Запрошенного голоса нет у провайдера."""


class AudioProcessingError(SpeechError):
    """ffmpeg или ffprobe не смогли обработать файл."""


@dataclass(frozen=True)
class Voice:
    name: str
    locale: str
    gender: str


@dataclass(frozen=True)
class SynthesisRequest:
    """Запрос синтеза. Рык применяется сервисом после синтеза, не провайдером."""

    text: str
    voice: str
    rate_percent: int = 0
    pitch_hz: int = 0
    growl: bool = False

    def __post_init__(self) -> None:
        if not MIN_RATE_PERCENT <= self.rate_percent <= MAX_RATE_PERCENT:
            raise ValueError(f"rate_percent вне диапазона {MIN_RATE_PERCENT}..{MAX_RATE_PERCENT}")
        if not MIN_PITCH_HZ <= self.pitch_hz <= MAX_PITCH_HZ:
            raise ValueError(f"pitch_hz вне диапазона {MIN_PITCH_HZ}..{MAX_PITCH_HZ}")


@dataclass(frozen=True)
class SynthesisResult:
    path: Path
    duration_seconds: float
    provider: str
    cached: bool
    growl: bool


@runtime_checkable
class SpeechProvider(Protocol):
    name: str
    max_text_length: int

    def list_voices(self) -> list[Voice]:
        """Голоса провайдера; не более одного сетевого запроса за процесс."""
        ...

    def synthesize(self, request: SynthesisRequest, target: Path) -> None:
        """Записать речь без обработки рыком в target."""
        ...
