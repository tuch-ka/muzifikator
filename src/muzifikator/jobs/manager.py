"""Менеджер задач: одна генерация одновременно."""

from __future__ import annotations

import logging
import threading

from .base import GenerationParams
from .pipeline import JobDeps, run_generation

log = logging.getLogger(__name__)


class JobManager:
    """Держит занятость движка и запускает пайплайн в отдельном потоке."""

    def __init__(self, deps: JobDeps) -> None:
        self.deps = deps
        self._lock = threading.Lock()
        self._busy_id: str | None = None

    @property
    def busy_id(self) -> str | None:
        with self._lock:
            return self._busy_id

    def reserve(self, generation_id: str) -> str | None:
        """Занять движок; вернуть id текущей задачи, если уже занято."""
        with self._lock:
            if self._busy_id is not None:
                return self._busy_id
            self._busy_id = generation_id
            return None

    def release(self, generation_id: str) -> None:
        with self._lock:
            if self._busy_id == generation_id:
                self._busy_id = None

    def start_reserved(self, generation_id: str, params: GenerationParams) -> None:
        """Запустить поток для заранее занятого слота."""
        thread = threading.Thread(
            target=self._run,
            args=(generation_id, params),
            name=f"job-{generation_id}",
            daemon=True,
        )
        thread.start()

    def submit(self, generation_id: str, params: GenerationParams) -> str | None:
        """Занять слот и запустить; вернуть id занявшей задачи, если занято."""
        busy = self.reserve(generation_id)
        if busy is not None:
            return busy
        self.start_reserved(generation_id, params)
        return None

    def _run(self, generation_id: str, params: GenerationParams) -> None:
        try:
            run_generation(generation_id, params, self.deps)
        except Exception:
            log.exception("необработанная ошибка задачи %s", generation_id)
        finally:
            self.release(generation_id)
