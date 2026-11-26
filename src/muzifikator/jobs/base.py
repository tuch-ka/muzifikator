"""Параметры задачи генерации."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationParams:
    text: str
    voice: str
    rate_percent: int = 0
    pitch_hz: int = 0
    growl: bool = False
    music_tags: str | None = None
    music_seed: int | None = None
    formats: tuple[str, ...] | None = None
