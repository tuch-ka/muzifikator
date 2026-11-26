"""Провайдер edge-tts: синтез и список голосов через официальную библиотеку."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import edge_tts

from .base import (
    SpeechError,
    SynthesisError,
    SynthesisRequest,
    UnknownVoiceError,
    Voice,
    VoiceListError,
)

log = logging.getLogger(__name__)

SYNTHESIS_TIMEOUT_SECONDS = 180.0
VOICE_LIST_TIMEOUT_SECONDS = 60.0


class EdgeTTSProvider:
    """Первый провайдер. Сеть — только endpoint edge-tts."""

    name = "edge"
    max_text_length = 3000

    def __init__(self) -> None:
        self._voices: list[Voice] | None = None

    def list_voices(self) -> list[Voice]:
        if self._voices is None:
            raw = self._call(edge_tts.list_voices(), VOICE_LIST_TIMEOUT_SECONDS, "список голосов")
            voices = [
                Voice(
                    name=item["ShortName"],
                    locale=item["Locale"],
                    gender=item["Gender"],
                )
                for item in raw
            ]
            if not voices:
                raise VoiceListError("edge-tts вернул пустой список голосов")
            self._voices = voices
            log.info("edge-tts: получено голосов %d", len(voices))
        return list(self._voices)

    def synthesize(self, request: SynthesisRequest, target: Path) -> None:
        known = {voice.name for voice in self.list_voices()}
        if request.voice not in known:
            raise UnknownVoiceError(f"голос не найден у edge-tts: {request.voice}")

        communicate = edge_tts.Communicate(
            request.text,
            request.voice,
            rate=f"{request.rate_percent:+d}%",
            pitch=f"{request.pitch_hz:+d}Hz",
        )
        self._call(communicate.save(str(target)), SYNTHESIS_TIMEOUT_SECONDS, "синтез")

    def _call(self, coroutine: Coroutine[Any, Any, Any], timeout: float, action: str) -> Any:
        try:
            return _run_sync(coroutine, timeout)
        except SpeechError:
            raise
        except Exception as exc:
            detail = str(exc) or "без подробностей"
            message = f"edge-tts ({action}): {detail}"
            if action == "список голосов":
                raise VoiceListError(message) from exc
            raise SynthesisError(message) from exc


def _run_sync(coroutine: Coroutine[Any, Any, Any], timeout: float) -> Any:
    """Выполнить корутину в отдельном цикле; изнутри работающего цикла — ошибка."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        coroutine.close()
        raise SpeechError("синхронный вызов edge-tts из работающего event loop не поддерживается")
    return asyncio.run(asyncio.wait_for(coroutine, timeout))
