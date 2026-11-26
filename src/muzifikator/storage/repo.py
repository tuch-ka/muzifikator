"""Операции чтения и записи. Коммит — на вызывающей стороне."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .models import STAGES, Generation, GenerationFile, Setting, new_id, utcnow

MISSING = object()
"""Признак отсутствия настройки, когда значение по умолчанию не передано."""


class GenerationNotFoundError(LookupError):
    """Записи с таким идентификатором нет."""


class InvalidTransitionError(RuntimeError):
    """Недопустимый переход статуса или стадии."""


def create_generation(
    session: Session,
    *,
    text: str,
    tts_provider: str | None = None,
    voice: str | None = None,
    music_tags: str | None = None,
    music_seed: int | None = None,
    generation_id: str | None = None,
) -> Generation:
    generation = Generation(
        id=generation_id or new_id(),
        created_at=utcnow(),
        text=text,
        tts_provider=tts_provider,
        voice=voice,
        music_tags=music_tags,
        music_seed=music_seed,
        status="pending",
    )
    session.add(generation)
    session.flush()
    return generation


def start_generation(session: Session, generation_id: str) -> Generation:
    generation = _require(session, generation_id)
    if generation.status != "pending":
        raise InvalidTransitionError(
            f"начать можно только запись в статусе pending, сейчас {generation.status}"
        )
    generation.status = "running"
    session.flush()
    return generation


def set_stage(session: Session, generation_id: str, stage: str) -> Generation:
    if stage not in STAGES:
        raise InvalidTransitionError(f"неизвестная стадия: {stage}")
    generation = _require(session, generation_id)
    if generation.status != "running":
        raise InvalidTransitionError(
            f"стадия допустима только в статусе running, сейчас {generation.status}"
        )
    generation.stage = stage
    session.flush()
    return generation


def finish_generation(
    session: Session,
    generation_id: str,
    *,
    output_path: str,
    duration_seconds: float,
) -> Generation:
    generation = _require(session, generation_id)
    if generation.status != "running":
        raise InvalidTransitionError(
            f"завершить можно только запись в статусе running, сейчас {generation.status}"
        )
    generation.status = "done"
    generation.finished_at = utcnow()
    generation.output_path = output_path
    generation.duration_seconds = duration_seconds
    session.flush()
    return generation


def fail_generation(session: Session, generation_id: str, *, error: str) -> Generation:
    if not error.strip():
        raise InvalidTransitionError("текст ошибки не может быть пустым")
    generation = _require(session, generation_id)
    if generation.status not in {"pending", "running"}:
        raise InvalidTransitionError(f"запись уже завершена со статусом {generation.status}")
    generation.status = "failed"
    generation.finished_at = utcnow()
    generation.error = error
    session.flush()
    return generation


def get_generation(session: Session, generation_id: str) -> Generation | None:
    return session.get(Generation, generation_id)


def list_generations(session: Session, *, limit: int = 50) -> list[Generation]:
    if limit < 1:
        raise ValueError("limit должен быть положительным")
    return list(session.query(Generation).order_by(Generation.created_at.desc()).limit(limit))


def add_generation_file(
    session: Session, generation_id: str, *, format: str, path: str
) -> GenerationFile:
    row = session.get(GenerationFile, (generation_id, format))
    if row is None:
        row = GenerationFile(generation_id=generation_id, format=format, path=path)
        session.add(row)
    else:
        row.path = path
    session.flush()
    return row


def get_generation_file(session: Session, generation_id: str, format: str) -> GenerationFile | None:
    return session.get(GenerationFile, (generation_id, format))


def list_generation_files(session: Session, generation_id: str) -> list[GenerationFile]:
    return list(
        session.query(GenerationFile)
        .filter(GenerationFile.generation_id == generation_id)
        .order_by(GenerationFile.format)
    )


def get_generation_files(session: Session, generation_id: str) -> dict[str, Path]:
    return {row.format: Path(row.path) for row in list_generation_files(session, generation_id)}


def fail_stale_generations(session: Session, *, reason: str) -> int:
    """Перевести все running в failed: задача прервана перезапуском."""
    stale = session.query(Generation).filter(Generation.status == "running").all()
    for generation in stale:
        generation.status = "failed"
        generation.finished_at = utcnow()
        generation.error = reason
    if stale:
        session.flush()
    return len(stale)


def set_setting(session: Session, key: str, value: Any) -> Setting:
    payload = json.dumps(value, ensure_ascii=False)
    setting = session.get(Setting, key)
    if setting is None:
        setting = Setting(key=key, value=payload, updated_at=utcnow())
        session.add(setting)
    else:
        setting.value = payload
        setting.updated_at = utcnow()
    session.flush()
    return setting


def get_setting(session: Session, key: str, default: Any = MISSING) -> Any:
    """Значение по ключу, default при отсутствии, MISSING если default не задан."""
    setting = session.get(Setting, key)
    if setting is None:
        return default
    return json.loads(setting.value)


def _require(session: Session, generation_id: str) -> Generation:
    generation = session.get(Generation, generation_id)
    if generation is None:
        raise GenerationNotFoundError(generation_id)
    return generation
