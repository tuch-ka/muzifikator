"""HTTP-приложение: сборка роутеров, health и восстановление после рестарта."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import metadata
from typing import Any

from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .api import SettingsStore, build_files_router, build_generations_router, build_settings_router
from .config import Settings
from .jobs import JobManager
from .preflight import PreflightResult
from .storage import fail_stale_generations

log = logging.getLogger(__name__)

STALE_REASON = "прервано перезапуском"


def app_version() -> str:
    """Версия пакета из метаданных; unknown, если метаданных нет."""
    try:
        return metadata.version("muzifikator")
    except metadata.PackageNotFoundError:
        return "unknown"


def create_app(
    preflight: PreflightResult,
    *,
    engine: Engine | None = None,
    session_factory: sessionmaker[Session] | None = None,
    jobs: JobManager | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Создать приложение из роутеров; тяжёлые зависимости приходят снаружи."""
    base = settings or Settings()

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

    store = (
        SettingsStore(
            session_factory,
            default_music_tags=base.music_prompt,
            default_formats=base.output_formats_list,
        )
        if session_factory is not None
        else None
    )

    app.include_router(
        build_generations_router(session_factory=session_factory, jobs=jobs, store=store)
    )
    app.include_router(build_settings_router(store))
    app.include_router(build_files_router(base.output_dir))

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

    return app
