"""Имена файлов, транслитерация и атомарная запись результатов."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

SLUG_LIMIT = 40
FALLBACK_SLUG = "audio"
SLUG_MAX_WORDS = 6
TEMP_PREFIX = ".tmp-"

_TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_DASHES = re.compile(r"-{2,}")


def slugify(text: str, *, limit: int = SLUG_LIMIT) -> str:
    """Латинский slug из начала текста: буквы, цифры, дефисы."""
    words = text.split()[:SLUG_MAX_WORDS]
    transliterated = "".join(_TRANSLIT.get(char, char) for char in " ".join(words).lower())
    slug = _NON_SLUG.sub("-", transliterated)
    slug = _DASHES.sub("-", slug).strip("-")
    slug = slug[:limit].strip("-")
    return slug or FALLBACK_SLUG


def build_stem(text: str, *, now: datetime) -> str:
    return f"{now:%Y%m%d-%H%M%S}-{slugify(text)}"


def plan_output_files(
    output_dir: Path, *, text: str, formats: Sequence[str], now: datetime
) -> dict[str, Path]:
    """Свободные имена для всех форматов; при коллизии — суффикс -2, -3."""
    stem = build_stem(text, now=now)
    counter = 1
    while True:
        candidate_stem = stem if counter == 1 else f"{stem}-{counter}"
        candidates = {fmt: output_dir / f"{candidate_stem}.{fmt}" for fmt in formats}
        if not any(path.exists() for path in candidates.values()):
            return candidates
        counter += 1


def temporary_path(output_dir: Path, suffix: str) -> Path:
    """Скрытый временный файл в выходном каталоге."""
    import tempfile

    handle, name = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=suffix, dir=output_dir)
    os.close(handle)
    return Path(name)


def replace_all(pairs: list[tuple[Path, Path]]) -> None:
    """Переместить готовые временные файлы на итоговые имена."""
    placed: list[Path] = []
    try:
        for source, target in pairs:
            os.replace(source, target)
            placed.append(target)
    except OSError:
        for target in placed:
            target.unlink(missing_ok=True)
        raise


def cleanup(paths: Sequence[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("не удалось удалить временный файл %s: %s", path, exc)
