"""HTTP-приложение: health-эндпоинт над снимком preflight."""

from __future__ import annotations

import logging
from importlib import metadata
from typing import Any

from fastapi import FastAPI

from .preflight import PreflightResult

log = logging.getLogger(__name__)


def app_version() -> str:
    """Версия пакета из метаданных; unknown, если метаданных нет."""
    try:
        return metadata.version("muzifikator")
    except metadata.PackageNotFoundError:
        return "unknown"


def create_app(preflight: PreflightResult) -> FastAPI:
    """Создать приложение с уже готовым снимком preflight."""
    app = FastAPI(title="muzifikator", version=app_version())
    app.state.preflight = preflight

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
