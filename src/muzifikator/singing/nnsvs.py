"""Бэкенд NNSVS: UST -> вокал WAV через вендоренный пайплайн в подпроцессе."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..paths import project_root
from .base import Note, SingingBackendError
from .ust import write_ust

TIMEOUT_SECONDS = 600.0


class NNSVSBackend:
    name = "nnsvs"

    def __init__(
        self,
        *,
        model_dir: Path,
        vendor_dir: Path | None = None,
        python: str | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self.model_dir = model_dir.resolve()
        self.vendor_dir = (vendor_dir or (project_root() / "vendor")).resolve()
        self.python = python or sys.executable
        self.timeout = timeout

    def sing(self, *, notes: list[Note], tempo: int, target: Path) -> None:
        if len(notes) < 2:
            raise SingingBackendError("NNSVS требует минимум две ноты")
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        ust_path = target.parent / "song.tmp"
        write_ust(
            ust_path,
            notes,
            voice_dir=self.model_dir,
            cache_dir=target.parent,
            tempo=tempo,
        )
        command = [
            self.python,
            "-m",
            "muzifikator.singing.worker",
            str(ust_path),
            str(target),
            str(self.vendor_dir),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SingingBackendError(f"NNSVS не завершился за {self.timeout:g} с") from exc
        except OSError as exc:
            raise SingingBackendError(f"не удалось запустить NNSVS: {exc}") from exc
        if completed.returncode != 0:
            detail = _last_line(completed.stderr) or _last_line(completed.stdout)
            raise SingingBackendError(
                f"NNSVS завершился с кодом {completed.returncode}"
                + (f": {detail}" if detail else "")
            )
        if not target.is_file():
            raise SingingBackendError("NNSVS не создал файл вокала")


def _last_line(output: str | None) -> str | None:
    if not output:
        return None
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return None
