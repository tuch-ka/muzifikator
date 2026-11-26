"""Контракты пения: запрос, результат, бэкенд, ошибки."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


class SingingError(RuntimeError):
    """Базовая ошибка пения."""


class SingingRequestError(SingingError):
    """Некорректный запрос пения."""


class SingingBackendError(SingingError):
    """Синтез вокала не удался."""


@dataclass(frozen=True)
class SingingRequest:
    lyrics: str
    tags: str = ""
    seed: int | None = None


@dataclass(frozen=True)
class SingingResult:
    path: Path
    duration_seconds: float
    seed: int


@dataclass(frozen=True)
class Note:
    """Нота для UST: слово кириллицей, высота, длина в тиках (480 — четверть)."""

    lyric: str
    midi: int
    length: int


@runtime_checkable
class SingingBackend(Protocol):
    name: str

    def sing(self, *, notes: list[Note], tempo: int, target: Path) -> None:
        """Синтезировать вокал по нотам в WAV-файл target."""
        ...
