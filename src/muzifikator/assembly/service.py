"""Сервис сборки: замеры, микс, экспорт, атомарная запись."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..media import MediaError, MediaTools
from .base import (
    DEFAULT_FORMATS,
    AssemblyRequest,
    AssemblyResult,
    EncodingError,
    InsufficientMusicError,
    OutputWriteError,
    normalize_formats,
)
from .files import cleanup, plan_output_files, replace_all, temporary_path
from .mix import Mixer, MixSettings

log = logging.getLogger(__name__)

_ENCODERS: dict[str, list[str]] = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
}


@dataclass(frozen=True)
class _Encoding:
    format: str
    path: Path


class AssemblyService:
    def __init__(
        self,
        *,
        ffmpeg_bin: str,
        ffprobe_bin: str,
        output_dir: Path,
        formats: Sequence[str] = DEFAULT_FORMATS,
        mix_settings: MixSettings | None = None,
        min_duration_seconds: float = 20.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.media = MediaTools(ffmpeg_bin=ffmpeg_bin, ffprobe_bin=ffprobe_bin)
        self.mixer = Mixer(self.media, mix_settings)
        self.output_dir = output_dir
        self.formats = normalize_formats(formats)
        self.min_duration_seconds = min_duration_seconds
        self.clock = clock or datetime.now

    @property
    def tail_seconds(self) -> float:
        return self.mixer.settings.tail_seconds

    def required_music_duration(self, speech_seconds: float) -> float:
        """Целевая длительность трека: не меньше речи с хвостом и минимума."""
        return max(speech_seconds + self.tail_seconds, self.min_duration_seconds)

    def render(self, request: AssemblyRequest) -> AssemblyResult:
        formats = normalize_formats(request.formats or self.formats)
        try:
            speech_duration = self.media.probe_duration(request.speech)
            music_duration = self.media.probe_duration(request.music)
        except MediaError as exc:
            raise OutputWriteError(f"не удалось прочитать вход: {exc}") from exc

        target_duration = self.required_music_duration(speech_duration)
        if music_duration + 0.05 < target_duration:
            raise InsufficientMusicError(
                f"музыка короче микса: {music_duration:.2f} с при нужных {target_duration:.2f} с"
            )

        target_dir = request.output_dir or self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        master = temporary_path(target_dir, ".wav")
        temporaries: list[Path] = [master]
        encodings: list[_Encoding] = []
        try:
            self.mixer.mix(
                request.speech,
                request.music,
                master,
                speech_duration=speech_duration,
                music_duration=music_duration,
                target_duration=target_duration,
            )
            for fmt in formats:
                path = temporary_path(target_dir, f".{fmt}")
                temporaries.append(path)
                encodings.append(_Encoding(format=fmt, path=path))
            self._encode(master, encodings)
            targets = plan_output_files(
                target_dir, text=request.text, formats=formats, now=self.clock()
            )
            try:
                replace_all([(item.path, targets[item.format]) for item in encodings])
            except OSError as exc:
                raise OutputWriteError(f"не удалось записать результат: {exc}") from exc
            duration = self.media.probe_duration(targets[formats[0]])
        finally:
            cleanup(temporaries)

        log.info("сборка: %s", ", ".join(str(path) for path in targets.values()))
        return AssemblyResult(files=targets, formats=formats, duration_seconds=duration)

    def _encode(self, master: Path, encodings: list[_Encoding]) -> None:
        command = [self.media.ffmpeg_bin, "-y", "-i", str(master)]
        for item in encodings:
            command.extend(["-ar", "44100", "-ac", "1", *_ENCODERS[item.format], str(item.path)])
        try:
            self.media.run(command, action="ffmpeg (экспорт)")
        except MediaError as exc:
            raise EncodingError(f"экспорт не удался: {exc}") from exc
