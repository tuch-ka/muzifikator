"""Общий слой ffmpeg/ffprobe: запуск, длительность, склейка, кроссфейд."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 30.0
FFMPEG_TIMEOUT_SECONDS = 300.0

ENCODERS: dict[str, list[str]] = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
}


class MediaError(RuntimeError):
    """ffmpeg или ffprobe не смогли выполнить операцию."""


@dataclass(frozen=True)
class MediaTools:
    """Операции поверх ffmpeg и ffprobe с уже разрешёнными путями бинарей."""

    ffmpeg_bin: str
    ffprobe_bin: str

    def run(
        self,
        command: list[str],
        *,
        timeout: float = FFMPEG_TIMEOUT_SECONDS,
        action: str = "ffmpeg",
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
            raise MediaError(f"{action}: бинарь не найден: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaError(f"{action}: не завершилось за {timeout:g} с") from exc
        except OSError as exc:
            raise MediaError(f"{action}: не удалось запустить: {exc}") from exc

        if completed.returncode != 0:
            detail = _last_line(completed.stderr)
            raise MediaError(
                f"{action}: код {completed.returncode}" + (f": {detail}" if detail else "")
            )
        return completed

    def probe_duration(self, path: Path) -> float:
        completed = self.run(
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
            raise MediaError(f"ffprobe не вернул длительность для {path}: {raw!r}") from exc
        if duration <= 0:
            raise MediaError(f"ffprobe вернул нулевую длительность для {path}")
        return duration

    def concat(
        self, sources: list[Path], target: Path, *, action: str = "ffmpeg (склейка)"
    ) -> None:
        if not sources:
            raise MediaError("нечего склеивать: пустой список файлов")
        if len(sources) == 1:
            target.write_bytes(sources[0].read_bytes())
            return
        list_file = target.parent / "concat.txt"
        lines = []
        for source in sources:
            escaped = str(source.resolve()).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.run(
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
                "4",
                str(target),
            ],
            action=action,
        )

    def mix_tracks(
        self,
        vocal: Path,
        backing: Path,
        target: Path,
        *,
        duration: float,
        vocal_gain: float = 1.0,
        backing_gain: float = 0.35,
        sample_rate: int = 44100,
        fade_out: float = 2.0,
    ) -> None:
        """Свести вокал и подложку: вокал главный, музыка фоном, loudnorm, fade-out."""
        fmt = f"aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=mono"
        fade_start = max(0.0, duration - fade_out) if fade_out > 0 else 0.0
        tail_filter = f",afade=t=out:st={fade_start:.3f}:d={fade_out}" if fade_out > 0 else ""
        graph = ";".join(
            [
                f"[0:a]{fmt},volume={vocal_gain}[v]",
                f"[1:a]{fmt},volume={backing_gain}[b]",
                (
                    "[v][b]amix=inputs=2:duration=longest:normalize=0,"
                    "loudnorm=I=-16:TP=-1.5:LRA=11"
                    f"{tail_filter}[out]"
                ),
            ]
        )
        self.run(
            [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(vocal),
                "-i",
                str(backing),
                "-filter_complex",
                graph,
                "-map",
                "[out]",
                "-t",
                f"{duration:.3f}",
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            action="ffmpeg (сведение)",
        )

    def encode(self, master: Path, encodings: list[tuple[str, Path]]) -> None:
        """Закодировать мастер в запрошенные форматы одной командой."""
        command = [self.ffmpeg_bin, "-y", "-i", str(master)]
        for fmt, path in encodings:
            command.extend(["-ar", "44100", "-ac", "1", *ENCODERS[fmt], str(path)])
        self.run(command, action="ffmpeg (экспорт)")

    def crossfade_concat(
        self,
        sources: list[Path],
        target: Path,
        *,
        crossfade_seconds: float = 2.0,
    ) -> None:
        """Склеить сегменты с перекрытием; выход — WAV PCM 16 бит."""
        if not sources:
            raise MediaError("нечего склеивать: пустой список файлов")
        if len(sources) == 1:
            target.write_bytes(sources[0].read_bytes())
            return

        command = [self.ffmpeg_bin, "-y"]
        for source in sources:
            command.extend(["-i", str(source)])

        filters: list[str] = []
        previous = "0:a"
        for index in range(1, len(sources)):
            output = f"a{index}"
            filters.append(
                f"[{previous}][{index}:a]acrossfade=d={crossfade_seconds}:c1=tri:c2=tri[{output}]"
            )
            previous = output
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                f"[{previous}]",
                "-c:a",
                "pcm_s16le",
                str(target),
            ]
        )
        self.run(command, action="ffmpeg (кроссфейд)")


def _last_line(output: str | None) -> str | None:
    if not output:
        return None
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return None
