"""Слой пения: процедурная мелодия, UST, NNSVS-бэкенд, сервис."""

from .base import (
    Note,
    SingingBackend,
    SingingBackendError,
    SingingError,
    SingingRequest,
    SingingRequestError,
    SingingResult,
)
from .melody import melody, words
from .nnsvs import NNSVSBackend
from .service import SingingPlan, SingingService
from .ust import render_ust, write_ust

__all__ = [
    "NNSVSBackend",
    "Note",
    "SingingBackend",
    "SingingBackendError",
    "SingingError",
    "SingingRequest",
    "SingingRequestError",
    "SingingPlan",
    "SingingResult",
    "SingingService",
    "melody",
    "render_ust",
    "words",
    "write_ust",
]
