"""HTTP-приложение: health, задачи генерации, голоса."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import metadata
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .assembly import UnknownFormatError, normalize_formats
from .jobs import (
    GenerationCreate,
    GenerationCreated,
    GenerationParams,
    GenerationView,
    JobManager,
    VoiceView,
)
from .preflight import PreflightResult
from .speech import VoiceListError
from .storage import (
    Generation,
    create_generation,
    fail_stale_generations,
    get_generation,
    get_generation_files,
    list_generations,
    new_id,
)

log = logging.getLogger(__name__)

STALE_REASON = "прервано перезапуском"


def app_version() -> str:
    """Версия пакета из метаданных; unknown, если метаданных нет."""
    try:
        return metadata.version("muzifikator")
    except metadata.PackageNotFoundError:
        return "unknown"


def _view(session: Session, generation: Generation) -> GenerationView:
    files = get_generation_files(session, generation.id)
    return GenerationView(
        id=generation.id,
        status=generation.status,
        stage=generation.stage,
        created_at=generation.created_at,
        finished_at=generation.finished_at,
        duration_seconds=generation.duration_seconds,
        error=generation.error,
        files={fmt: str(path) for fmt, path in files.items()},
    )


def create_app(
    preflight: PreflightResult,
    *,
    engine: Engine | None = None,
    session_factory: sessionmaker[Session] | None = None,
    jobs: JobManager | None = None,
) -> FastAPI:
    """Создать приложение с preflight, хранилищем и менеджером задач."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if session_factory is not None:
            try:
                with session_factory() as session:
                    stale = fail_stale_generations(session, reason=STALE_REASON)
                    session.commit()
                if stale:
                    log.warning("задач, прерванных перезапуском: %d", stale)
            except Exception as exc:  # старт не должен падать из-за уборки
                log.error("не удалось сбросить прерванные задачи: %s", exc)
        yield

    app = FastAPI(title="muzifikator", version=app_version(), lifespan=lifespan)
    app.state.preflight = preflight
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.jobs = jobs

    def require_jobs() -> JobManager:
        if jobs is None:
            raise HTTPException(status_code=503, detail="задачи не сконфигурированы")
        return jobs

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        snapshot: PreflightResult = app.state.preflight
        return {
            "status": "ok",
            "app_version": app.version,
            "binaries": {
                binary.name: {
                    "available": binary.available,
                    "path": binary.path,
                    "version": binary.version,
                }
                for binary in snapshot.binaries
            },
        }

    @app.get("/api/voices", response_model=list[VoiceView])
    def voices() -> list[VoiceView]:
        manager = require_jobs()
        try:
            return [
                VoiceView(name=voice.name, locale=voice.locale, gender=voice.gender)
                for voice in manager.deps.speech.list_voices()
            ]
        except VoiceListError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/generations", response_model=GenerationCreated, status_code=202)
    def create_generation_endpoint(payload: GenerationCreate) -> GenerationCreated:
        manager = require_jobs()
        if session_factory is None:
            raise HTTPException(status_code=503, detail="хранилище не сконфигурировано")
        try:
            formats = normalize_formats(payload.formats)
        except UnknownFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            known_voices = {voice.name for voice in manager.deps.speech.list_voices()}
        except VoiceListError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if payload.voice not in known_voices:
            raise HTTPException(status_code=400, detail=f"голос не найден: {payload.voice}")

        generation_id = new_id()
        busy = manager.reserve(generation_id)
        if busy is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "уже выполняется другая генерация",
                    "generation_id": busy,
                },
            )

        params = GenerationParams(
            text=payload.text,
            voice=payload.voice,
            rate_percent=payload.rate_percent,
            pitch_hz=payload.pitch_hz,
            growl=payload.growl,
            music_tags=payload.music_tags,
            music_seed=payload.music_seed,
            formats=formats,
        )
        try:
            with session_factory() as session:
                create_generation(
                    session,
                    text=payload.text,
                    voice=payload.voice,
                    tts_provider="edge",
                    music_tags=payload.music_tags,
                    music_seed=payload.music_seed,
                    generation_id=generation_id,
                )
                session.commit()
        except Exception:
            manager.release(generation_id)
            raise

        manager.start_reserved(generation_id, params)
        return GenerationCreated(id=generation_id, status="pending")

    @app.get("/api/generations/{generation_id}", response_model=GenerationView)
    def generation_state(generation_id: str) -> GenerationView:
        if session_factory is None:
            raise HTTPException(status_code=503, detail="хранилище не сконфигурировано")
        with session_factory() as session:
            generation = get_generation(session, generation_id)
            if generation is None:
                raise HTTPException(status_code=404, detail="задача не найдена")
            return _view(session, generation)

    @app.get("/api/generations", response_model=list[GenerationView])
    def generation_history(
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[GenerationView]:
        if session_factory is None:
            raise HTTPException(status_code=503, detail="хранилище не сконфигурировано")
        with session_factory() as session:
            return [_view(session, item) for item in list_generations(session, limit=limit)]

    return app
