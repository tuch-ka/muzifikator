"""Файловый кэш речи: ключи, sidecar-метаданные, атомарная запись, LRU-лимит."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .base import SynthesisRequest

log = logging.getLogger(__name__)

_KEY_LENGTH = 32
MIB = 1024 * 1024


class CacheError(RuntimeError):
    """Кэш нельзя прочитать или записать."""


@dataclass(frozen=True)
class CacheMetadata:
    key: str
    provider: str
    voice: str
    rate_percent: int
    pitch_hz: int
    growl: bool
    duration_seconds: float
    text_length: int
    text_sha256: str
    created_at: str

    @classmethod
    def build(
        cls,
        *,
        key: str,
        provider: str,
        request: SynthesisRequest,
        duration_seconds: float,
    ) -> CacheMetadata:
        return cls(
            key=key,
            provider=provider,
            voice=request.voice,
            rate_percent=request.rate_percent,
            pitch_hz=request.pitch_hz,
            growl=request.growl,
            duration_seconds=duration_seconds,
            text_length=len(request.text),
            text_sha256=hashlib.sha256(request.text.encode("utf-8")).hexdigest(),
            created_at=datetime.now(UTC).isoformat(),
        )


@dataclass(frozen=True)
class CacheEntry:
    audio: Path
    sidecar: Path
    metadata: CacheMetadata


def cache_key(provider: str, request: SynthesisRequest) -> str:
    """Ключ по провайдеру, голосу, параметрам и тексту."""
    payload = json.dumps(
        {
            "provider": provider,
            "voice": request.voice,
            "rate_percent": request.rate_percent,
            "pitch_hz": request.pitch_hz,
            "growl": request.growl,
            "text": request.text,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:_KEY_LENGTH]


def audio_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.mp3"


def sidecar_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def lookup(cache_dir: Path, key: str) -> CacheEntry | None:
    """Запись кэша, если на диске есть и аудио, и валидный sidecar."""
    audio = audio_path(cache_dir, key)
    sidecar = sidecar_path(cache_dir, key)
    if not audio.is_file() or not sidecar.is_file():
        return None
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        metadata = CacheMetadata(**raw)
    except (OSError, ValueError, TypeError) as exc:
        log.warning("кэш: sidecar %s не читается (%s), запись пересоздастся", sidecar, exc)
        return None
    if metadata.key != key:
        log.warning("кэш: sidecar %s относится к другому ключу, запись пересоздастся", sidecar)
        return None
    return CacheEntry(audio=audio, sidecar=sidecar, metadata=metadata)


def touch(entry: CacheEntry) -> None:
    """Отметить обращение для LRU; ошибка не критична."""
    try:
        os.utime(entry.audio)
    except OSError as exc:
        log.warning("кэш: не удалось обновить время обращения %s: %s", entry.audio, exc)


def store(cache_dir: Path, *, key: str, audio: Path, metadata: CacheMetadata) -> CacheEntry:
    """Перенести готовое аудио в кэш и записать sidecar; сначала аудио, потом sidecar."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    final_audio = audio_path(cache_dir, key)
    final_sidecar = sidecar_path(cache_dir, key)
    try:
        os.replace(audio, final_audio)
        _write_json_atomic(final_sidecar, asdict(metadata))
    except OSError as exc:
        raise CacheError(f"не удалось записать кэш {final_audio}: {exc}") from exc
    return CacheEntry(audio=final_audio, sidecar=final_sidecar, metadata=metadata)


def temporary_directory(cache_dir: Path) -> Path:
    """Временный каталог внутри кэша: перенос в кэш остаётся атомарным."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".tmp-", dir=cache_dir))


def directory_size(cache_dir: Path) -> int:
    if not cache_dir.is_dir():
        return 0
    total = 0
    for path in cache_dir.glob("*"):
        if path.is_file() and path.suffix in {".mp3", ".json"}:
            total += path.stat().st_size
    return total


def enforce_limit(cache_dir: Path, limit_bytes: int, *, keep_key: str | None = None) -> list[str]:
    """Удалить самые давние записи, пока размер не опустится до лимита.

    `limit_bytes <= 0` отключает вытеснение. Ошибки удаления логируются и не
    прерывают работу: кэш — вспомогательные данные.
    """
    removed: list[str] = []
    if limit_bytes <= 0 or not cache_dir.is_dir():
        return removed

    size = directory_size(cache_dir)
    if size <= limit_bytes:
        return removed

    candidates = sorted(
        (path for path in cache_dir.glob("*.mp3") if path.stem != keep_key),
        key=lambda path: path.stat().st_mtime,
    )
    for audio in candidates:
        if size <= limit_bytes:
            break
        sidecar = audio.with_suffix(".json")
        freed = 0
        for path in (audio, sidecar):
            try:
                path_size = path.stat().st_size
                path.unlink()
                freed += path_size
            except FileNotFoundError:
                continue
            except OSError as exc:
                log.warning("кэш: не удалось удалить %s: %s", path, exc)
        if freed:
            size -= freed
            removed.append(audio.stem)
            log.info("кэш: вытеснена запись %s (%d байт)", audio.stem, freed)
    return removed


def limit_bytes_from_mib(limit_mib: int) -> int:
    return limit_mib * MIB


def remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
