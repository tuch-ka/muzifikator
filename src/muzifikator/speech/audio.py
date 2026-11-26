"""Рычащая обработка голоса поверх общего ffmpeg-слоя."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..media import FFMPEG_TIMEOUT_SECONDS, MediaError, MediaTools
from .base import AudioProcessingError

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
class AudioTools(MediaTools):
    """ffmpeg/ffprobe для речи: общие операции плюс «рык»."""

    def run(
        self,
        command: list[str],
        *,
        timeout: float = FFMPEG_TIMEOUT_SECONDS,
        action: str = "ffmpeg",
    ) -> subprocess.CompletedProcess[str]:
        try:
            return super().run(command, timeout=timeout, action=action)
        except MediaError as exc:
            raise AudioProcessingError(str(exc)) from exc

    def growl(self, source: Path, target: Path) -> None:
        self.run(
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
                "4",
                str(target),
            ],
            timeout=FFMPEG_TIMEOUT_SECONDS,
            action="ffmpeg (рык)",
        )
