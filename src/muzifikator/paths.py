"""Проверка путей внутри разрешённого корня."""

from __future__ import annotations

from pathlib import Path


class PathOutsideRootError(ValueError):
    """Путь выходит за пределы корневого каталога."""


def resolve_within(root: Path, raw: str) -> Path:
    """Разрешить относительный путь внутри корня.

    Пустая строка означает сам корень. Принимает и нормализует вложенность,
    отклоняет абсолютные пути, нулевые байты и выход за корень (включая симлинки).
    """
    if "\x00" in raw:
        raise PathOutsideRootError("недопустимый путь")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise PathOutsideRootError("путь должен быть относительным")
    base = root.resolve()
    resolved = (base / candidate).resolve()
    if resolved != base and base not in resolved.parents:
        raise PathOutsideRootError("путь вне корневого каталога")
    return resolved
