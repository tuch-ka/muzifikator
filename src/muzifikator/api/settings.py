"""API пользовательских настроек."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .settings_store import InvalidSettingError, SettingsStore, UnknownSettingError


def build_settings_router(store: SettingsStore | None) -> APIRouter:
    router = APIRouter()

    def require_store() -> SettingsStore:
        if store is None:
            raise HTTPException(status_code=503, detail="настройки не сконфигурированы")
        return store

    @router.get("/api/settings")
    def read_settings() -> dict[str, Any]:
        return require_store().read()

    @router.patch("/api/settings")
    def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
        current = require_store()
        try:
            return current.update(payload)
        except (UnknownSettingError, InvalidSettingError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
