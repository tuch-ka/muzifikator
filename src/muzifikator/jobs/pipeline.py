"""Пайплайн генерации: стадии tts → music → mix и запись хода в базу."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from ..assembly import AssemblyRequest, AssemblyService
from ..music import MusicRequest, MusicService
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


@dataclass(frozen=True)
class JobDeps:
    session_factory: sessionmaker[Session]
    speech: SpeechService
    music: MusicService
    assembly: AssemblyService
    output_dir: Path
    tail_seconds: float
    formats: tuple[str, ...]


def run_generation(generation_id: str, params: GenerationParams, deps: JobDeps) -> None:
    """Выполнить задачу целиком; ошибки сохраняются в записи, наружу не летят."""
    with deps.session_factory() as session:
        try:
            start_generation(session, generation_id)
            set_stage(session, generation_id, "tts")
            session.commit()

            speech = deps.speech.synthesize(
                SynthesisRequest(
                    text=params.text,
                    voice=params.voice,
                    rate_percent=params.rate_percent,
                    pitch_hz=params.pitch_hz,
                    growl=params.growl,
                )
            )

            set_stage(session, generation_id, "music")
            session.commit()
            deps.output_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".tmp-music-", dir=deps.output_dir) as workdir:
                music = deps.music.generate(
                    MusicRequest(
                        duration_seconds=speech.duration_seconds
                        + deps.tail_seconds
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
                        subdir=params.folder,
                    )
                )

            for fmt, path in result.files.items():
                add_generation_file(session, generation_id, format=fmt, path=str(path))
            primary = result.files.get("mp3") or next(iter(result.files.values()))
            finish_generation(
                session,
                generation_id,
                output_path=str(primary),
                duration_seconds=result.duration_seconds,
            )
            session.commit()
            log.info("задача %s завершена", generation_id)
        except Exception as exc:
            session.rollback()
            log.exception("задача %s упала", generation_id)
            message = str(exc) or type(exc).__name__
            fail_generation(session, generation_id, error=message)
            session.commit()
