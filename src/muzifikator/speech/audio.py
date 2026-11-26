"""ffmpeg/ffprobe: длительность, склейка порций, обработка «рык»."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import AudioProcessingError

log = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 30.0
FFMPEG_TIMEOUT_SECONDS = 300.0
GOOD_ENOUGH_QUALITY = "4"

PITCH_FACTOR = 0.82
BASE_SAMPLE_RATE = 48000
GROWL_FILTER = (
    f"aresample={BASE_SAMPLE_RATE},"
    f"asetrate={int(BASE_SAMPLE_RATE * PITCH_FACTOR)},"
    f"atempo={1 / PITCH_FACTOR:.5f},"
    "acrusher=bits=8:mode=log:mix=0.35,"
    "equalizer=f=110:width_type=h:width=100:g=5,"
    "alimiter=limit=0.95"
)


@dataclass(frozen=True)
class AudioTools:
    """Операции поверх ffmpeg и ffprobe с уже разрешёнными путями бинарей."""

    ffmpeg_bin: str
    ffprobe_bin: str

    def probe_duration(self, path: Path) -> float:
        completed = self._run(
            [
                self.ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            timeout=PROBE_TIMEOUT_SECONDS,
            action="ffprobe",
        )
        raw = completed.stdout.strip()
        try:
            duration = float(raw)
        except ValueError as exc:
            raise AudioProcessingError(
                f"ffprobe не вернул длительность для {path}: {raw!r}"
            ) from exc
        if duration <= 0:
            raise AudioProcessingError(f"ffprobe вернул нулевую длительность для {path}")
        return duration

    def concat(self, sources: list[Path], target: Path) -> None:
        if not sources:
            raise AudioProcessingError("нечего склеивать: пустой список файлов")
        if len(sources) == 1:
            target.write_bytes(sources[0].read_bytes())
            return
        list_file = target.parent / "concat.txt"
        lines = []
        for source in sources:
            escaped = str(source.resolve()).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._run(
            [
                self.ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:a",
                "libmp3lame",
                "-q:a",
                GOOD_ENOUGH_QUALITY,
                str(target),
            ],
            action="ffmpeg (склейка)",
        )

    def growl(self, source: Path, target: Path) -> None:
        self._run(
            [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(source),
                "-af",
                GROWL_FILTER,
                "-c:a",
                "libmp3lame",
                "-q:a",
                GOOD_ENOUGH_QUALITY,
                str(target),
            ],
            action="ffmpeg (рык)",
        )

    def _run(
        self,
        command: list[str],
        *,
        timeout: float = FFMPEG_TIMEOUT_SECONDS,
        action: str,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AudioProcessingError(f"{action}: бинарь не найден: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioProcessingError(f"{action}: не завершилось за {timeout:g} с") from exc
        except OSError as exc:
            raise AudioProcessingError(f"{action}: не удалось запустить: {exc}") from exc

        if completed.returncode != 0:
            detail = _last_line(completed.stderr)
            raise AudioProcessingError(
                f"{action}: код {completed.returncode}" + (f": {detail}" if detail else "")
            )
        return completed


def _last_line(output: str | None) -> str | None:
    if not output:
        return None
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return None
