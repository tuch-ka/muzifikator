"""API задач генерации: постановка, опрос, история, голоса."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session, sessionmaker

from ..assembly import UnknownFormatError, normalize_formats
from ..jobs import (
    GenerationCreate,
    GenerationCreated,
    GenerationParams,
    GenerationView,
    JobManager,
    VoiceView,
)
from ..speech import VoiceListError
from ..storage import (
    Generation,
    create_generation,
    get_generation,
    get_generation_files,
    list_generations,
    new_id,
)
from .settings_store import SettingsStore


def build_generations_router(
    *,
    session_factory: sessionmaker[Session] | None,
    jobs: JobManager | None,
    store: SettingsStore | None,
) -> APIRouter:
    router = APIRouter()

    def require_jobs() -> JobManager:
        if jobs is None:
            raise HTTPException(status_code=503, detail="задачи не сконфигурированы")
        return jobs

    def require_session_factory() -> sessionmaker[Session]:
        if session_factory is None:
            raise HTTPException(status_code=503, detail="хранилище не сконфигурировано")
        return session_factory

    def view(session: Session, generation: Generation) -> GenerationView:
        files = get_generation_files(session, generation.id)
        return GenerationView(
            id=generation.id,
            status=generation.status,
            mode=generation.mode,
            stage=generation.stage,
            created_at=generation.created_at,
            finished_at=generation.finished_at,
            duration_seconds=generation.duration_seconds,
            error=generation.error,
            files={fmt: str(path) for fmt, path in files.items()},
        )

    @router.get("/api/voices", response_model=list[VoiceView])
    def voices() -> list[VoiceView]:
        manager = require_jobs()
        try:
            return [
                VoiceView(name=voice.name, locale=voice.locale, gender=voice.gender)
                for voice in manager.deps.speech.list_voices()
            ]
        except VoiceListError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/api/generations", response_model=GenerationCreated, status_code=202)
    def create_generation_endpoint(payload: GenerationCreate) -> GenerationCreated:
        manager = require_jobs()
        factory = require_session_factory()
        if store is None:
            raise HTTPException(status_code=503, detail="настройки не сконфигурированы")

        settings = store.read()
        mode = payload.mode
        if mode not in {"song", "narrated"}:
            raise HTTPException(status_code=400, detail=f"неизвестный режим: {mode}")
        voice: str | None = None
        if mode == "narrated":
            voice = payload.voice or settings["tts_voice"]
            if not voice:
                raise HTTPException(
                    status_code=422,
                    detail="голос не указан и не сохранён в настройках",
                )
        music_tags = (
            payload.music_tags if payload.music_tags is not None else settings["music_tags"]
        )
        rate_percent = (
            payload.rate_percent if payload.rate_percent is not None else settings["rate_percent"]
        )
        pitch_hz = payload.pitch_hz if payload.pitch_hz is not None else settings["pitch_hz"]
        growl = payload.growl if payload.growl is not None else settings["growl"]
        requested_formats = (
            payload.formats if payload.formats is not None else settings["output_formats"]
        )
        try:
            formats = normalize_formats(requested_formats)
        except UnknownFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if mode == "narrated":
            try:
                known_voices = {item.name for item in manager.deps.speech.list_voices()}
            except VoiceListError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            if voice not in known_voices:
                raise HTTPException(status_code=400, detail=f"голос не найден: {voice}")

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
            voice=voice,
            rate_percent=rate_percent,
            pitch_hz=pitch_hz,
            growl=growl,
            music_tags=music_tags,
            music_seed=payload.music_seed,
            formats=formats,
            mode=mode,
        )
        try:
            with factory() as session:
                create_generation(
                    session,
                    text=payload.text,
                    voice=voice,
                    tts_provider="edge",
                    music_tags=music_tags,
                    music_seed=payload.music_seed,
                    mode=mode,
                    generation_id=generation_id,
                )
                session.commit()
        except Exception:
            manager.release(generation_id)
            raise

        manager.start_reserved(generation_id, params)
        return GenerationCreated(id=generation_id, status="pending")

    @router.get("/api/generations/{generation_id}", response_model=GenerationView)
    def generation_state(generation_id: str) -> GenerationView:
        factory = require_session_factory()
        with factory() as session:
            generation = get_generation(session, generation_id)
            if generation is None:
                raise HTTPException(status_code=404, detail="задача не найдена")
            return view(session, generation)

    @router.get("/api/generations", response_model=list[GenerationView])
    def generation_history(
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[GenerationView]:
        factory = require_session_factory()
        with factory() as session:
            return [view(session, item) for item in list_generations(session, limit=limit)]

    return router
