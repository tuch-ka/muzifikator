"""Библиотека файлов: список из базы, проигрывание, открытие и удаление."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from ..paths import StorageDirError, home_root, is_inside, storage_dir
from ..storage import (
    Generation,
    GenerationFile,
    get_generation,
    get_generation_file,
    list_generation_files,
)
from .settings_store import SettingsStore

log = logging.getLogger(__name__)

MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
}
REVEAL_TIMEOUT_SECONDS = 5.0
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class FileEntry(BaseModel):
    generation_id: str
    format: str
    name: str
    path: str
    exists: bool
    size: int | None = None
    created_at: datetime
    duration_seconds: float | None = None


class FilePage(BaseModel):
    files: list[FileEntry]
    has_more: bool


class StorageInfo(BaseModel):
    path: str


class BrowseEntry(BaseModel):
    name: str
    path: str
    writable: bool


class BrowseListing(BaseModel):
    path: str
    parent: str | None
    entries: list[BrowseEntry]


def media_type(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def reveal_command(path: Path, platform: str | None = None) -> list[str]:
    """Команда ОС, открывающая файл в менеджере; для каталога — сам каталог."""
    current = platform or sys.platform
    if current == "darwin":
        return ["open", "-R", str(path)]
    if current.startswith("win"):
        return ["explorer", f"/select,{path}"]
    target = path if path.is_dir() else path.parent
    return ["xdg-open", str(target)]


def build_library_router(
    *,
    session_factory: sessionmaker[Session] | None,
    store: SettingsStore | None,
) -> APIRouter:
    router = APIRouter()

    def require_session_factory() -> sessionmaker[Session]:
        if session_factory is None:
            raise HTTPException(status_code=503, detail="хранилище не сконфигурировано")
        return session_factory

    def require_store() -> SettingsStore:
        if store is None:
            raise HTTPException(status_code=503, detail="настройки не сконфигурированы")
        return store

    def entry(generation: Generation, file: GenerationFile) -> FileEntry:
        path = Path(file.path)
        exists = path.is_file()
        return FileEntry(
            generation_id=generation.id,
            format=file.format,
            name=path.name,
            path=str(path),
            exists=exists,
            size=path.stat().st_size if exists else None,
            created_at=generation.created_at,
            duration_seconds=generation.duration_seconds,
        )

    def find_file(generation_id: str, format: str) -> tuple[Generation, Path]:
        factory = require_session_factory()
        with factory() as session:
            generation = get_generation(session, generation_id)
            if generation is None:
                raise HTTPException(status_code=404, detail="генерация не найдена")
            file = get_generation_file(session, generation_id, format)
            if file is None:
                raise HTTPException(status_code=404, detail="файл не найден")
            return generation, Path(file.path)

    @router.get("/api/files", response_model=FilePage)
    def list_files(
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
    ) -> FilePage:
        factory = require_session_factory()
        with factory() as session:
            rows = (
                session.query(GenerationFile, Generation)
                .join(Generation, GenerationFile.generation_id == Generation.id)
                .order_by(Generation.created_at.desc(), GenerationFile.format)
                .offset(offset)
                .limit(limit + 1)
                .all()
            )
            has_more = len(rows) > limit
            files = [entry(generation, file) for file, generation in rows[:limit]]
        return FilePage(files=files, has_more=has_more)

    @router.get("/api/generations/{generation_id}/files/{format}/media")
    def file_media(generation_id: str, format: str) -> FileResponse:
        _, path = find_file(generation_id, format)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="файл отсутствует на диске")
        return FileResponse(path, media_type=media_type(path))

    @router.post("/api/generations/{generation_id}/files/{format}/reveal", status_code=204)
    def file_reveal(generation_id: str, format: str) -> None:
        _, path = find_file(generation_id, format)
        if not path.exists():
            raise HTTPException(status_code=404, detail="файл отсутствует на диске")
        command = reveal_command(path)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=REVEAL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(status_code=502, detail=f"не удалось открыть: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip().splitlines()
            message = detail[-1] if detail else f"код {completed.returncode}"
            raise HTTPException(status_code=502, detail=f"не удалось открыть: {message}")

    @router.delete("/api/generations/{generation_id}", status_code=204)
    def delete_generation(generation_id: str) -> None:
        factory = require_session_factory()
        with factory() as session:
            generation = get_generation(session, generation_id)
            if generation is None:
                raise HTTPException(status_code=404, detail="генерация не найдена")
            paths = [Path(item.path) for item in list_generation_files(session, generation_id)]
            for path in paths:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise HTTPException(
                        status_code=502, detail=f"не удалось удалить {path}: {exc}"
                    ) from exc
            session.delete(generation)
            session.commit()

    @router.get("/api/storage", response_model=StorageInfo)
    def storage_info() -> StorageInfo:
        return StorageInfo(path=str(require_store().effective_output_dir()))

    @router.get("/api/storage/browse", response_model=BrowseListing)
    def storage_browse(path: str = Query(default="")) -> BrowseListing:
        root = home_root()
        raw = path.strip() or str(root)
        try:
            target = storage_dir(raw)
        except StorageDirError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not is_inside(target, root):
            raise HTTPException(status_code=400, detail="путь вне домашнего каталога")
        entries = []
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir():
                continue
            entries.append(
                BrowseEntry(
                    name=child.name,
                    path=str(child),
                    writable=os.access(child, os.W_OK),
                )
            )
        parent = None if target == root else str(target.parent)
        return BrowseListing(path=str(target), parent=parent, entries=entries)

    return router
