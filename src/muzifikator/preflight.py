"""Preflight внешних бинарей ffmpeg и ffprobe."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings

VERSION_TIMEOUT_SECONDS = 5.0
REQUIRED_ENCODERS = ("libmp3lame", "aac")

_ENV_HINT = {"ffmpeg": "FFMPEG_BIN", "ffprobe": "FFPROBE_BIN"}
_VERSION_RE = re.compile(r"\bversion\s+(\d[^\s]*)")
_ENCODER_LINE_RE = re.compile(r"^\s*[A-Z.]{6}\s+(\S+)")

INSTALL_HINT = """\
ffmpeg и ffprobe обязательны: ими режется, склеивается и нормализуется аудио.
Установите ffmpeg вместе с ffprobe:
  macOS:         brew install ffmpeg
  Debian/Ubuntu: sudo apt install ffmpeg
  Fedora:        sudo dnf install ffmpeg (репозиторий RPM Fusion)
Если бинари лежат в нестандартном месте, задайте FFMPEG_BIN и FFPROBE_BIN.
Сборка ffmpeg должна содержать энкодеры MP3 (libmp3lame) и M4A (aac): сборки
Homebrew и apt их содержат, минимальные сборки — нет."""

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BinaryStatus:
    """Результат проверки одного бинаря."""

    name: str
    available: bool
    path: str | None = None
    version: str | None = None
    error: str | None = None
    missing_encoders: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreflightResult:
    """Снимок проверки окружения; не меняется в течение жизни процесса."""

    ffmpeg: BinaryStatus
    ffprobe: BinaryStatus

    @property
    def binaries(self) -> tuple[BinaryStatus, ...]:
        return (self.ffmpeg, self.ffprobe)

    @property
    def ok(self) -> bool:
        return all(
            binary.available and binary.error is None and not binary.missing_encoders
            for binary in self.binaries
        )


def run_preflight(settings: Settings) -> PreflightResult:
    """Проверить оба бинаря один раз и вернуть снимок."""
    ffmpeg = _check_binary("ffmpeg", settings.ffmpeg_bin)
    ffprobe = _check_binary("ffprobe", settings.ffprobe_bin)
    return PreflightResult(ffmpeg=ffmpeg, ffprobe=ffprobe)


def format_failure(result: PreflightResult) -> str:
    """Собрать одно сообщение со всеми проблемами и подсказкой по установке."""
    lines = ["Не удалось запустить приложение: не работает внешнее окружение."]
    for binary in result.binaries:
        if not binary.available or binary.error is not None:
            lines.append(f"  - {binary.name}: {binary.error}")
        elif binary.missing_encoders:
            missing = ", ".join(binary.missing_encoders)
            lines.append(f"  - {binary.name}: нет энкодеров {missing}")
    lines.extend(["", INSTALL_HINT])
    return "\n".join(lines)


def _check_binary(name: str, configured: Path | None) -> BinaryStatus:
    path, resolution_error = _resolve_path(name, configured)
    if resolution_error is not None or path is None:
        log.warning("preflight %s: %s", name, resolution_error)
        return BinaryStatus(
            name=name,
            available=False,
            path=str(configured) if configured is not None else None,
            error=resolution_error or "путь к бинарю не определён",
        )
    return _probe_version(name, path)


def _resolve_path(name: str, configured: Path | None) -> tuple[Path | None, str | None]:
    if configured is not None:
        exists = configured.is_file()
        if not exists:
            return None, f"путь из настроек не найден: {configured}"
        if not os.access(configured, os.X_OK):
            return None, f"файл из настроек не исполняемый: {configured}"
        return configured, None

    found = shutil.which(name)
    if found is None:
        return None, f"не найден в PATH, а {_ENV_HINT[name]} не задан"
    return Path(found), None


def _probe_version(name: str, path: Path) -> BinaryStatus:
    try:
        completed = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        error = f"не ответил за {VERSION_TIMEOUT_SECONDS:g} с (таймаут)"
        log.warning("preflight %s: %s", name, error)
        return BinaryStatus(name=name, available=False, path=str(path), error=error)
    except OSError as exc:
        error = f"не удалось запустить: {exc}"
        log.warning("preflight %s: %s", name, error)
        return BinaryStatus(name=name, available=False, path=str(path), error=error)

    if completed.returncode != 0:
        detail = _last_line(completed.stderr or completed.stdout)
        error = f"код возврата {completed.returncode}"
        if detail:
            error = f"{error}: {detail}"
        log.warning("preflight %s: %s", name, error)
        return BinaryStatus(name=name, available=False, path=str(path), error=error)

    version = _extract_version(f"{completed.stdout}\n{completed.stderr}")
    missing: tuple[str, ...] = ()
    encoder_error: str | None = None
    if name == "ffmpeg":
        try:
            missing = _missing_encoders(path)
        except subprocess.TimeoutExpired:
            encoder_error = (
                f"не удалось получить список энкодеров: таймаут {VERSION_TIMEOUT_SECONDS:g} с"
            )
        except (OSError, RuntimeError) as exc:
            encoder_error = f"не удалось получить список энкодеров: {exc}"
        if missing:
            log.warning("preflight %s: нет энкодеров %s", name, ", ".join(missing))
    log.info("preflight %s: %s, версия %s", name, path, version or "неизвестно")
    return BinaryStatus(
        name=name,
        available=True,
        path=str(path),
        version=version,
        error=encoder_error,
        missing_encoders=missing,
    )


def _last_line(output: str | None) -> str | None:
    if not output:
        return None
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _missing_encoders(path: Path) -> tuple[str, ...]:
    completed = subprocess.run(
        [str(path), "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        timeout=VERSION_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        detail = _last_line(completed.stderr)
        raise RuntimeError(
            f"ffmpeg -encoders завершился с кодом {completed.returncode}"
            + (f": {detail}" if detail else "")
        )
    available = {
        match.group(1)
        for line in completed.stdout.splitlines()
        if (match := _ENCODER_LINE_RE.match(line))
    }
    return tuple(name for name in REQUIRED_ENCODERS if name not in available)


def _extract_version(output: str) -> str | None:
    match = _VERSION_RE.search(output)
    return match.group(1) if match else None
