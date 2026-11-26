"""Слой сборки: микс речи и музыки и экспорт результатов."""

from .base import (
    DEFAULT_FORMATS,
    FADE_SECONDS,
    SUPPORTED_FORMATS,
    TAIL_SECONDS,
    AssemblyError,
    AssemblyRequest,
    AssemblyResult,
    EncodingError,
    InsufficientMusicError,
    InvalidFolderError,
    OutputWriteError,
    UnknownFormatError,
    normalize_formats,
)
from .files import build_stem, plan_output_files, slugify
from .mix import Mixer, MixSettings
from .service import AssemblyService

__all__ = [
    "DEFAULT_FORMATS",
    "FADE_SECONDS",
    "SUPPORTED_FORMATS",
    "TAIL_SECONDS",
    "AssemblyError",
    "AssemblyRequest",
    "AssemblyResult",
    "AssemblyService",
    "EncodingError",
    "InsufficientMusicError",
    "InvalidFolderError",
    "MixSettings",
    "Mixer",
    "OutputWriteError",
    "UnknownFormatError",
    "build_stem",
    "normalize_formats",
    "plan_output_files",
    "slugify",
]
