"""Отдача статического интерфейса из пакета."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def web_directory() -> Path:
    return WEB_DIR


def build_ui_router() -> APIRouter:
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", media_type="text/html")

    return router
