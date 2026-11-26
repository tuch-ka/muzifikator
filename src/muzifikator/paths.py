"""Правила путей: абсолютные значения и каталог хранения."""

from __future__ import annotations

import os
from pathlib import Path


class StorageDirError(ValueError):
    """Каталог хранения не проходит валидацию."""


def project_root() -> Path:
    """Корень репозитория: там лежат alembic.ini и migrations/."""
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "alembic.ini").is_file():
        return candidate
    return Path.cwd()


def expand(raw: str | Path) -> Path:
    """Раскрыть ~ и привести к абсолютному виду без требования существования."""
    return Path(raw).expanduser().resolve()


def is_inside(child: Path, parent: Path) -> bool:
    resolved_child = child.resolve()
    resolved_parent = parent.resolve()
    return resolved_child == resolved_parent or resolved_parent in resolved_child.parents


def home_root() -> Path:
    return Path.home().resolve()


def storage_dir(raw: str | Path) -> Path:
    """Проверить каталог хранения: абсолютный, существует, каталог, доступен на запись."""
    text = str(raw).strip()
    if not text:
        raise StorageDirError("путь не задан")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise StorageDirError("путь должен быть абсолютным")
    resolved = path.resolve()
    if not resolved.exists():
        raise StorageDirError("каталога не существует")
    if not resolved.is_dir():
        raise StorageDirError("путь не является каталогом")
    if not os.access(resolved, os.W_OK):
        raise StorageDirError("каталог недоступен на запись")
    return resolved
