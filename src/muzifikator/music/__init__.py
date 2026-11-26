"""Слой музыки: генерация подложки MusicGen по промпту, длительности и seed."""

from .backend import TransformersBackend
from .base import (
    CROSSFADE_SECONDS,
    MIN_DURATION_SECONDS,
    MODEL_SAMPLE_RATE,
    WINDOW_SECONDS,
    MusicBackend,
    MusicError,
    MusicGenerationError,
    MusicModelError,
    MusicProvider,
    MusicRequest,
    MusicRequestError,
    MusicResourceError,
    MusicResult,
)
from .musicgen import MusicGenProvider, write_wav
from .service import MusicService, plan_segments

__all__ = [
    "CROSSFADE_SECONDS",
    "MIN_DURATION_SECONDS",
    "MODEL_SAMPLE_RATE",
    "WINDOW_SECONDS",
    "MusicBackend",
    "MusicError",
    "MusicGenProvider",
    "MusicGenerationError",
    "MusicModelError",
    "MusicProvider",
    "MusicRequest",
    "MusicRequestError",
    "MusicResourceError",
    "MusicService",
    "MusicResult",
    "TransformersBackend",
    "plan_segments",
    "write_wav",
]
