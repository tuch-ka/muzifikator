"""Слой речи: провайдеры синтеза, кэш, ffmpeg-обработка."""

from .audio import AudioTools
from .base import (
    AudioProcessingError,
    EmptyTextError,
    SpeechError,
    SpeechProvider,
    SynthesisError,
    SynthesisRequest,
    SynthesisResult,
    UnknownVoiceError,
    Voice,
    VoiceListError,
)
from .cache import CacheEntry, CacheMetadata, cache_key
from .edge import EdgeTTSProvider
from .service import SpeechService, split_text

__all__ = [
    "AudioProcessingError",
    "AudioTools",
    "CacheEntry",
    "CacheMetadata",
    "EdgeTTSProvider",
    "EmptyTextError",
    "SpeechError",
    "SpeechProvider",
    "SpeechService",
    "SynthesisError",
    "SynthesisRequest",
    "SynthesisResult",
    "UnknownVoiceError",
    "Voice",
    "VoiceListError",
    "cache_key",
    "split_text",
]
