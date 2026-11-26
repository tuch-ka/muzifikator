"""Пайплайн генерации: narrated (речь+музыка) и song (пение+подложка)."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from ..assembly import AssemblyRequest, AssemblyService
from ..assembly.files import cleanup, plan_output_files, replace_all, temporary_path
from ..music import MusicRequest, MusicService
from ..singing import SingingRequest, SingingService
from ..speech import SpeechService, SynthesisRequest
from ..storage import (
    add_generation_file,
    fail_generation,
    finish_generation,
    set_stage,
    start_generation,
)
from .base import GenerationParams

log = logging.getLogger(__name__)

MUSIC_TAIL_RESERVE_SECONDS = 0.3
BACKING_GAIN = 0.6
VOCAL_GAIN = 0.8


@dataclass(frozen=True)
class JobDeps:
    session_factory: sessionmaker[Session]
    speech: SpeechService
    music: MusicService
    assembly: AssemblyService
    singing: SingingService
    resolve_output_dir: Callable[[], Path]
    tail_seconds: float
    formats: tuple[str, ...]


def run_generation(generation_id: str, params: GenerationParams, deps: JobDeps) -> None:
    """Выполнить задачу целиком; ошибки сохраняются в записи, наружу не летят."""
    with deps.session_factory() as session:
        try:
            start_generation(session, generation_id)
            if params.mode == "song":
                files, duration = _run_song(session, generation_id, params, deps)
            else:
                files, duration = _run_narrated(session, generation_id, params, deps)

            for fmt, path in files.items():
                add_generation_file(session, generation_id, format=fmt, path=str(path))
            primary = files.get("mp3") or next(iter(files.values()))
            finish_generation(
                session,
                generation_id,
                output_path=str(primary),
                duration_seconds=duration,
            )
            session.commit()
            log.info("задача %s завершена", generation_id)
        except Exception as exc:
            session.rollback()
            log.exception("задача %s упала", generation_id)
            message = str(exc) or type(exc).__name__
            fail_generation(session, generation_id, error=message)
            session.commit()


def _run_narrated(
    session: Session, generation_id: str, params: GenerationParams, deps: JobDeps
) -> tuple[dict[str, Path], float]:
    set_stage(session, generation_id, "tts")
    session.commit()
    speech = deps.speech.synthesize(
        SynthesisRequest(
            text=params.text,
            voice=params.voice or "",
            rate_percent=params.rate_percent,
            pitch_hz=params.pitch_hz,
            growl=params.growl,
        )
    )

    set_stage(session, generation_id, "music")
    session.commit()
    output_dir = deps.resolve_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tmp-music-", dir=output_dir) as workdir:
        music = deps.music.generate(
            MusicRequest(
                duration_seconds=deps.assembly.required_music_duration(speech.duration_seconds)
                + MUSIC_TAIL_RESERVE_SECONDS,
                prompt=params.music_tags,
                seed=params.music_seed,
            ),
            Path(workdir),
        )

        set_stage(session, generation_id, "mix")
        session.commit()
        result = deps.assembly.render(
            AssemblyRequest(
                speech=speech.path,
                music=music.path,
                text=params.text,
                formats=params.formats,
                output_dir=output_dir,
            )
        )
    return result.files, result.duration_seconds


def _run_song(
    session: Session, generation_id: str, params: GenerationParams, deps: JobDeps
) -> tuple[dict[str, Path], float]:
    set_stage(session, generation_id, "tts")
    session.commit()
    plan = deps.singing.plan(
        SingingRequest(
            lyrics=params.text,
            tags=params.music_tags or "",
            seed=params.music_seed,
        )
    )

    output_dir = deps.resolve_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    formats = params.formats or deps.formats
    media = deps.assembly.media

    with tempfile.TemporaryDirectory(prefix=".tmp-song-", dir=output_dir) as workdir:
        vocal = deps.singing.render(plan, Path(workdir))

        set_stage(session, generation_id, "music")
        session.commit()
        total = deps.assembly.required_music_duration(vocal.duration_seconds)
        backing = deps.music.generate(
            MusicRequest(
                duration_seconds=total + MUSIC_TAIL_RESERVE_SECONDS,
                prompt=params.music_tags,
                seed=plan.seed,
            ),
            Path(workdir),
        )

        set_stage(session, generation_id, "mix")
        session.commit()
        mixed = Path(workdir) / "mixed.wav"
        media.mix_tracks(
            vocal.path,
            backing.path,
            mixed,
            duration=total,
            vocal_gain=VOCAL_GAIN,
            backing_gain=BACKING_GAIN,
        )
        duration = media.probe_duration(mixed)

        targets = plan_output_files(
            output_dir, text=params.text, formats=formats, now=datetime.now()
        )
        temporaries: list[Path] = []
        pairs: list[tuple[Path, Path]] = []
        try:
            encodings: list[tuple[str, Path]] = []
            for fmt in formats:
                temp = temporary_path(output_dir, f".{fmt}")
                temporaries.append(temp)
                encodings.append((fmt, temp))
                pairs.append((temp, targets[fmt]))
            media.encode(mixed, encodings)
            replace_all(pairs)
        finally:
            cleanup(temporaries)
    return targets, duration
