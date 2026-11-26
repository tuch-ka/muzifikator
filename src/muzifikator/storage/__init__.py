"""Хранилище: модели, движок и операции доступа к данным."""

from .db import StorageError, create_db_engine, create_session_factory, init_storage
from .models import STAGES, STATUSES, Base, Generation, Setting, new_id, utcnow
from .repo import (
    MISSING,
    GenerationNotFoundError,
    InvalidTransitionError,
    create_generation,
    fail_generation,
    finish_generation,
    get_generation,
    get_setting,
    list_generations,
    set_setting,
    set_stage,
    start_generation,
)

__all__ = [
    "MISSING",
    "STATUSES",
    "STAGES",
    "Base",
    "Generation",
    "GenerationNotFoundError",
    "InvalidTransitionError",
    "Setting",
    "StorageError",
    "create_db_engine",
    "create_generation",
    "create_session_factory",
    "fail_generation",
    "finish_generation",
    "get_generation",
    "get_setting",
    "init_storage",
    "list_generations",
    "new_id",
    "set_setting",
    "set_stage",
    "start_generation",
    "utcnow",
]
