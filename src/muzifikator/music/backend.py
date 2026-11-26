"""Бэкенд MusicGen: ленивая загрузка модели и генерация сегмента.

`torch` и `transformers` импортируются внутри методов: пакет `muzifikator.music`
должен импортироваться в окружении без этих тяжёлых зависимостей (CI ставит
проект с `--no-install-package torch`).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .base import (
    MODEL_SAMPLE_RATE,
    MusicGenerationError,
    MusicModelError,
    MusicResourceError,
)

if TYPE_CHECKING:
    from transformers import MusicgenForConditionalGeneration

log = logging.getLogger(__name__)

TOKENS_PER_SECOND = 50
GUIDANCE_SCALE = 3.0
# MusicGen отдаёт примерно на 0,06 с меньше запрошенного при любом размере сегмента.
SEGMENT_MARGIN_SECONDS = 0.25
_MEMORY_MARKERS = ("out of memory", "not enough memory", "mps backend out of memory")


class TransformersBackend:
    """Обёртка над `transformers`: одна модель в памяти на процесс."""

    def __init__(self, model_name: str, *, models_dir: Path, device: str = "auto") -> None:
        self.model_name = model_name
        self.models_dir = models_dir
        self.requested_device = device
        self._model: MusicgenForConditionalGeneration | None = None
        self._processor: Any | None = None
        self._device: str | None = None

    @property
    def device(self) -> str:
        if self._device is None:
            self._device = self._resolve_device()
        return self._device

    def load(self) -> None:
        if self._model is not None:
            return
        torch, auto_processor, model_class = _import_ml()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        log.info("музыка: загрузка модели %s на %s", self.model_name, self.device)
        try:
            self._processor = auto_processor.from_pretrained(
                self.model_name, cache_dir=str(self.models_dir)
            )
            self._model = model_class.from_pretrained(
                self.model_name,
                cache_dir=str(self.models_dir),
                dtype=torch.float32,
            ).to(self.device)
            self._model.eval()
        except Exception as exc:
            self._model = None
            self._processor = None
            raise MusicModelError(f"не удалось загрузить модель {self.model_name}: {exc}") from exc
        log.info("музыка: модель загружена")

    def generate(self, *, prompt: str, seconds: float, seed: int) -> np.ndarray:
        self.load()
        torch, _auto_processor, _model_class = _import_ml()
        assert self._processor is not None and self._model is not None
        tokens = max(
            TOKENS_PER_SECOND,
            int(round((seconds + SEGMENT_MARGIN_SECONDS) * TOKENS_PER_SECOND)),
        )
        log.info("музыка: сегмент %.1f с, seed %d, токенов %d", seconds, seed, tokens)
        try:
            inputs = self._processor(text=[prompt], padding=True, return_tensors="pt")
            moved = {name: value.to(self.device) for name, value in inputs.items()}
            torch.manual_seed(seed)
            with torch.inference_mode():
                audio = self._model.generate(
                    **moved,
                    do_sample=True,
                    guidance_scale=GUIDANCE_SCALE,
                    max_new_tokens=tokens,
                )
            samples: np.ndarray = audio[0, 0].to("cpu").numpy().astype(np.float32)
            return samples
        except RuntimeError as exc:
            message = str(exc).lower()
            if any(marker in message for marker in _MEMORY_MARKERS):
                raise MusicResourceError(
                    f"не хватило памяти для сегмента {seconds:.1f} с: {exc}"
                ) from exc
            raise MusicGenerationError(f"генерация не удалась: {exc}") from exc
        except Exception as exc:
            raise MusicGenerationError(f"генерация не удалась: {exc}") from exc

    @property
    def sample_rate(self) -> int:
        return MODEL_SAMPLE_RATE

    def _resolve_device(self) -> str:
        if self.requested_device != "auto":
            return self.requested_device
        torch, _auto_processor, _model_class = _import_ml()
        return "mps" if torch.backends.mps.is_available() else "cpu"


def _import_ml() -> tuple[Any, Any, Any]:
    """Импортировать тяжёлые зависимости с понятной ошибкой при их отсутствии."""
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
    except ImportError as exc:
        raise MusicModelError(
            "для генерации музыки нужны torch и transformers; установите их через `uv sync`"
        ) from exc
    return torch, AutoProcessor, MusicgenForConditionalGeneration
