"""Листинг файлов внутри выходного каталога с защитой путей."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..paths import PathOutsideRootError, resolve_within


class FileEntry(BaseModel):
    name: str
    path: str
    kind: str
    size: int | None = None
    modified_at: datetime


class FileListing(BaseModel):
    root: str
    path: str
    entries: list[FileEntry]


def build_files_router(output_dir: Path) -> APIRouter:
    router = APIRouter()
    root = output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    @router.get("/api/files", response_model=FileListing)
    def list_files(path: str = Query(default="")) -> FileListing:
        try:
            target = resolve_within(root, path)
        except PathOutsideRootError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not target.exists():
            raise HTTPException(status_code=404, detail="каталог не найден")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="путь не является каталогом")
        return FileListing(
            root=str(root),
            path=_relative(root, target),
            entries=_entries(root, target),
        )

    return router


def _relative(root: Path, target: Path) -> str:
    if target == root:
        return ""
    return target.relative_to(root).as_posix()


def _entries(root: Path, target: Path) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for child in target.iterdir():
        try:
            stat = child.stat()
        except OSError:
            continue
        is_dir = child.is_dir()
        entries.append(
            FileEntry(
                name=child.name,
                path=(child.relative_to(root)).as_posix(),
                kind="dir" if is_dir else "file",
                size=None if is_dir else stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )
        )
    entries.sort(key=lambda entry: (0 if entry.kind == "dir" else 1, entry.name.lower()))
    return entries
