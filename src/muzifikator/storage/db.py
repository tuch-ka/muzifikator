"""Движок, сессии и инициализация хранилища (каталог + миграции)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings

log = logging.getLogger(__name__)

_BUSY_TIMEOUT_MS = 5000


class StorageError(RuntimeError):
    """Хранилище нельзя инициализировать: путь, права, миграции."""


def project_root() -> Path:
    """Корень репозитория: там лежат alembic.ini и migrations/."""
    candidate = Path(__file__).resolve().parents[3]
    if (candidate / "alembic.ini").is_file():
        return candidate
    return Path.cwd()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_db_engine(db_path: Path) -> Engine:
    """Движок SQLite с прагмами, рассчитанными на один процесс и polling."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _apply_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        cursor.close()

    return engine


def alembic_config(db_path: Path, *, configure_logging: bool = False) -> Config:
    """Конфиг Alembic с путём к базе из настроек приложения."""
    config = Config(str(project_root() / "alembic.ini"))
    config.set_main_option("script_location", str(project_root() / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    config.attributes["configure_logging"] = configure_logging
    return config


def init_storage(settings: Settings) -> Engine:
    """Создать каталог базы, движок и довести схему до последней ревизии."""
    db_path = settings.db_path
    log.info("хранилище: %s", db_path)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_db_engine(db_path)
        command.upgrade(alembic_config(db_path), "head")
    except (OSError, SQLAlchemyError, CommandError, ValueError) as exc:
        raise StorageError(str(exc)) from exc
    log.info("хранилище: схема на последней ревизии")
    return engine
