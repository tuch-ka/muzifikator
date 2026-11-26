"""Сервис речи: кэш, порции, склейка, рык, длительность."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from pathlib import Path

from . import cache
from .audio import AudioTools
from .base import (
    EmptyTextError,
    SpeechProvider,
    SynthesisRequest,
    SynthesisResult,
    Voice,
)

log = logging.getLogger(__name__)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])\s+")


class SpeechService:
    def __init__(
        self,
        provider: SpeechProvider,
        *,
        cache_dir: Path,
        ffmpeg_bin: str,
        ffprobe_bin: str,
        cache_limit_mib: int = 200,
    ) -> None:
        self.provider = provider
        self.cache_dir = cache_dir
        self.cache_limit_mib = cache_limit_mib
        self.audio = AudioTools(ffmpeg_bin=ffmpeg_bin, ffprobe_bin=ffprobe_bin)

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        if not request.text.strip():
            raise EmptyTextError("нечего озвучивать: пустой текст")

        key = cache.cache_key(self.provider.name, request)
        hit = cache.lookup(self.cache_dir, key)
        if hit is not None:
            cache.touch(hit)
            log.info("кэш: попадание %s (%.2f с)", key, hit.metadata.duration_seconds)
            return SynthesisResult(
                path=hit.audio,
                duration_seconds=hit.metadata.duration_seconds,
                provider=self.provider.name,
                cached=True,
                growl=request.growl,
            )

        chunks = split_text(request.text, self.provider.max_text_length)
        if len(chunks) > 1:
            log.info("текст разбит на %d порций", len(chunks))

        workdir = cache.temporary_directory(self.cache_dir)
        try:
            parts = self._synthesize_chunks(request, chunks, workdir)
            combined = workdir / "combined.mp3"
            self.audio.concat(parts, combined)
            if request.growl:
                growled = workdir / "growled.mp3"
                self.audio.growl(combined, growled)
                final = growled
            else:
                final = combined

            duration = self.audio.probe_duration(final)
            metadata = cache.CacheMetadata.build(
                key=key,
                provider=self.provider.name,
                request=request,
                duration_seconds=duration,
            )
            entry = cache.store(self.cache_dir, key=key, audio=final, metadata=metadata)
        finally:
            cache.remove_tree(workdir)

        self._enforce_limit(key)
        log.info("синтез: %s, %.2f с", key, duration)
        return SynthesisResult(
            path=entry.audio,
            duration_seconds=duration,
            provider=self.provider.name,
            cached=False,
            growl=request.growl,
        )

    def list_voices(self) -> list[Voice]:
        return self.provider.list_voices()

    def _synthesize_chunks(
        self, request: SynthesisRequest, chunks: list[str], workdir: Path
    ) -> list[Path]:
        parts: list[Path] = []
        for index, chunk in enumerate(chunks):
            part = workdir / f"part-{index:03d}.mp3"
            self.provider.synthesize(replace(request, text=chunk), part)
            parts.append(part)
        return parts

    def _enforce_limit(self, key: str) -> None:
        try:
            cache.enforce_limit(
                self.cache_dir,
                cache.limit_bytes_from_mib(self.cache_limit_mib),
                keep_key=key,
            )
        except Exception as exc:  # кэш вспомогательный: синтез уже удался
            log.warning("кэш: не удалось применить лимит: %s", exc)


def split_text(text: str, limit: int) -> list[str]:
    """Разбить текст по границам предложений, не превышая limit символов."""
    if limit <= 0:
        raise ValueError("limit должен быть положительным")
    normalized = text.strip()
    if not normalized:
        raise EmptyTextError("нечего озвучивать: пустой текст")
    if len(normalized) <= limit:
        return [normalized]

    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_BOUNDARY.split(normalized):
        for piece in _split_by_words(sentence, limit):
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > limit:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _split_by_words(unit: str, limit: int) -> list[str]:
    if len(unit) <= limit:
        return [unit]
    pieces: list[str] = []
    current = ""
    for word in unit.split():
        while len(word) > limit:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:limit])
            word = word[limit:]
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces
