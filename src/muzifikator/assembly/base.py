"""Контракты слоя сборки: запросы, результаты, форматы, ошибки."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..config import SUPPORTED_OUTPUT_FORMATS

OutputFormat = str
SUPPORTED_FORMATS: tuple[str, ...] = SUPPORTED_OUTPUT_FORMATS
DEFAULT_FORMATS: tuple[str, ...] = SUPPORTED_OUTPUT_FORMATS
TAIL_SECONDS = 2.0
FADE_SECONDS = 2.0


class AssemblyError(RuntimeError):
    """Базовая ошибка сборки."""


class InsufficientMusicError(AssemblyError):
    """Музыка короче, чем нужно для микса с хвостом."""


class EncodingError(AssemblyError):
    """Кодирование итоговых форматов не удалось."""


class UnknownFormatError(AssemblyError):
    """Запрошен неизвестный формат вывода."""


class OutputWriteError(AssemblyError):
    """Не удалось записать итоговые файлы."""


def normalize_formats(formats: Sequence[str] | None) -> tuple[str, ...]:
    """Проверить набор форматов, убрать повторы и привести к нижнему регистру."""
    if formats is None:
        return DEFAULT_FORMATS
    normalized: list[str] = []
    for raw in formats:
        value = raw.strip().lower()
        if not value:
            continue
        if value not in SUPPORTED_FORMATS:
            raise UnknownFormatError(
                f"неизвестный формат: {raw}; допустимы: {', '.join(SUPPORTED_FORMATS)}"
            )
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise UnknownFormatError("нужен хотя бы один формат вывода")
    return tuple(normalized)


@dataclass(frozen=True)
class AssemblyRequest:
    speech: Path
    music: Path
    text: str
    formats: tuple[str, ...] | None = None
    output_dir: Path | None = None


@dataclass(frozen=True)
class AssemblyResult:
    files: dict[str, Path]
    formats: tuple[str, ...]
    duration_seconds: float
