"""Сервис пения: лирика и теги -> вокал WAV."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from .base import (
    Note,
    SingingBackend,
    SingingBackendError,
    SingingRequest,
    SingingRequestError,
    SingingResult,
)
from .melody import melody

log = logging.getLogger(__name__)

DEFAULT_TEMPO = 120


@dataclass(frozen=True)
class SingingPlan:
    notes: list[Note]
    seed: int
    tempo: int


class SingingService:
    def __init__(self, backend: SingingBackend, *, tempo: int = DEFAULT_TEMPO) -> None:
        self.backend = backend
        self.tempo = tempo

    def plan(self, request: SingingRequest) -> SingingPlan:
        if not request.lyrics.strip():
            raise SingingRequestError("нечего петь: пустая лирика")
        seed = request.seed if request.seed is not None else secrets.randbelow(2**32)
        notes = melody(request.lyrics, tags=request.tags, seed=seed, tempo=self.tempo)
        if len(notes) < 2:
            raise SingingRequestError("не удалось построить мелодию")
        return SingingPlan(notes=notes, seed=seed, tempo=self.tempo)

    def render(self, plan: SingingPlan, workdir: Path) -> SingingResult:
        workdir.mkdir(parents=True, exist_ok=True)
        target = workdir / "vocal.wav"
        log.info("пение: %d нот, seed %d", len(plan.notes), plan.seed)
        self.backend.sing(notes=plan.notes, tempo=plan.tempo, target=target)
        try:
            info = sf.info(str(target))
        except RuntimeError as exc:
            raise SingingBackendError(f"вокал не читается: {exc}") from exc
        return SingingResult(path=target, duration_seconds=info.duration, seed=plan.seed)

    def sing(self, request: SingingRequest, workdir: Path) -> SingingResult:
        return self.render(self.plan(request), workdir)
