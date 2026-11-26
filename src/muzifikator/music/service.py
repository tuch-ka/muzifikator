"""Сервис музыки: план сегментов, seed, сборка, длительность."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ..media import MediaTools
from .base import (
    CROSSFADE_SECONDS,
    MIN_DURATION_SECONDS,
    WINDOW_SECONDS,
    MusicError,
    MusicGenerationError,
    MusicProvider,
    MusicRequest,
    MusicRequestError,
    MusicResult,
)

log = logging.getLogger(__name__)

MAX_SEGMENTS = 100


@dataclass(frozen=True)
class _SegmentPlan:
    lengths: list[float]

    @property
    def total(self) -> float:
        return sum(self.lengths) - CROSSFADE_SECONDS * (len(self.lengths) - 1)


def plan_segments(
    duration: float,
    *,
    window: float = WINDOW_SECONDS,
    crossfade: float = CROSSFADE_SECONDS,
) -> list[float]:
    """Длины сегментов так, чтобы после кроссфейдов вышло не меньше duration."""
    if duration < MIN_DURATION_SECONDS:
        raise MusicRequestError(f"длительность должна быть не меньше {MIN_DURATION_SECONDS:g} с")
    if crossfade >= window:
        raise ValueError("кроссфейд должен быть меньше окна модели")

    lengths: list[float] = []
    assembled = 0.0
    while assembled < duration - 1e-9:
        overlap = crossfade if lengths else 0.0
        remaining = duration - assembled
        length = min(window, remaining + overlap)
        length = max(MIN_DURATION_SECONDS, length)
        lengths.append(length)
        assembled = sum(lengths) - crossfade * (len(lengths) - 1)
        if len(lengths) > MAX_SEGMENTS:
            raise MusicRequestError("слишком длинный запрос: больше 100 сегментов")
    return lengths


class MusicService:
    def __init__(
        self,
        provider: MusicProvider,
        *,
        ffmpeg_bin: str,
        ffprobe_bin: str,
        default_prompt: str,
        model_name: str,
        crossfade_seconds: float = CROSSFADE_SECONDS,
    ) -> None:
        self.provider = provider
        self.default_prompt = default_prompt
        self.model_name = model_name
        self.crossfade_seconds = crossfade_seconds
        self.media = MediaTools(ffmpeg_bin=ffmpeg_bin, ffprobe_bin=ffprobe_bin)

    def generate(self, request: MusicRequest, workdir: Path) -> MusicResult:
        prompt = (request.prompt or "").strip() or self.default_prompt
        seed = request.seed if request.seed is not None else secrets.randbelow(2**32)
        lengths = plan_segments(request.duration_seconds, crossfade=self.crossfade_seconds)
        workdir.mkdir(parents=True, exist_ok=True)
        log.info(
            "музыка: %.1f с, сегментов %d, seed %d, промпт %r",
            request.duration_seconds,
            len(lengths),
            seed,
            prompt,
        )

        parts: list[Path] = []
        final = workdir / f"music-{seed}-{uuid4().hex[:8]}.wav"
        try:
            for index, seconds in enumerate(lengths):
                part = workdir / f"music-part-{index:03d}-{uuid4().hex[:6]}.wav"
                self.provider.segment(
                    prompt=prompt, seconds=seconds, seed=seed + index, target=part
                )
                parts.append(part)

            self.media.crossfade_concat(parts, final, crossfade_seconds=self.crossfade_seconds)
            duration = self.media.probe_duration(final)
        except MusicError:
            final.unlink(missing_ok=True)
            raise
        finally:
            for part in parts:
                part.unlink(missing_ok=True)

        if duration + 1e-6 < request.duration_seconds:
            final.unlink(missing_ok=True)
            raise MusicGenerationError(
                f"трек короче запрошенного: {duration:.2f} с "
                f"вместо {request.duration_seconds:.2f} с"
            )

        return MusicResult(
            path=final,
            duration_seconds=duration,
            seed=seed,
            prompt=prompt,
            model=self.model_name,
            segments=len(lengths),
        )
