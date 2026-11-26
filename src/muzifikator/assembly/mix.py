"""Сведение речи и музыки: дакинг, фейды, нормализация громкости."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..media import MediaTools
from .base import FADE_SECONDS, TAIL_SECONDS, InsufficientMusicError

log = logging.getLogger(__name__)

DURATION_TOLERANCE = 0.05


@dataclass(frozen=True)
class MixSettings:
    sample_rate: int = 44100
    tail_seconds: float = TAIL_SECONDS
    fade_seconds: float = FADE_SECONDS
    music_level: float = 0.7
    duck_threshold: float = 0.02
    duck_ratio: int = 8
    duck_attack_ms: int = 20
    duck_release_ms: int = 350
    loudness_lufs: float = -16.0
    true_peak_db: float = -1.5
    loudness_range: float = 11.0


class Mixer:
    """Один ffmpeg-проход: музыка с фейдами и дакингом плюс речь."""

    def __init__(self, media: MediaTools, settings: MixSettings | None = None) -> None:
        self.media = media
        self.settings = settings or MixSettings()

    def mix(
        self,
        speech: Path,
        music: Path,
        target: Path,
        *,
        speech_duration: float,
        music_duration: float,
    ) -> None:
        s = self.settings
        needed = speech_duration + s.tail_seconds
        if music_duration + DURATION_TOLERANCE < needed:
            raise InsufficientMusicError(
                f"музыка короче микса: {music_duration:.2f} с при нужных {needed:.2f} с"
            )

        fade_out_start = max(0.0, music_duration - s.fade_seconds)
        format_in = f"aresample={s.sample_rate},aformat=sample_fmts=fltp:channel_layouts=mono"
        graph = ";".join(
            [
                f"[0:a]{format_in},asplit=2[sp][sp2]",
                # Без apad sidechaincompress замолкает вместе с речью и режет музыку.
                f"[sp]apad=whole_dur={music_duration:.3f}[sc]",
                (
                    f"[1:a]{format_in},"
                    f"afade=t=in:st=0:d={s.fade_seconds},"
                    f"volume={s.music_level},"
                    f"afade=t=out:st={fade_out_start:.3f}:d={s.fade_seconds}[mus]"
                ),
                (
                    f"[mus][sc]sidechaincompress="
                    f"threshold={s.duck_threshold}:"
                    f"ratio={s.duck_ratio}:"
                    f"attack={s.duck_attack_ms}:"
                    f"release={s.duck_release_ms}[duck]"
                ),
                (
                    f"[duck][sp2]amix=inputs=2:duration=longest:normalize=0,"
                    f"loudnorm=I={s.loudness_lufs}:TP={s.true_peak_db}:LRA={s.loudness_range}[out]"
                ),
            ]
        )

        log.info(
            "микс: речь %.2f с, музыка %.2f с, хвост %.1f с",
            speech_duration,
            music_duration,
            s.tail_seconds,
        )
        self.media.run(
            [
                self.media.ffmpeg_bin,
                "-y",
                "-i",
                str(speech),
                "-i",
                str(music),
                "-filter_complex",
                graph,
                "-map",
                "[out]",
                "-t",
                f"{needed:.3f}",
                "-ar",
                str(s.sample_rate),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            action="ffmpeg (микс)",
        )
