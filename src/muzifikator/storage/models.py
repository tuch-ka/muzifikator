"""Модели хранилища: генерации и сохранённые настройки."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

STATUSES = ("pending", "running", "done", "failed")
TERMINAL_STATUSES = frozenset({"done", "failed"})
STAGES = ("tts", "music", "mix")


def utcnow() -> datetime:
    """Текущее время в UTC с зоной."""
    return datetime.now(UTC)


def new_id() -> str:
    """Идентификатор генерации: uuid4 без дефисов."""
    return uuid.uuid4().hex


class UTCDateTime(TypeDecorator[datetime]):
    """Хранит наивное UTC, читает aware-UTC.

    SQLite не сохраняет смещение, поэтому зона приводится на границе слоя.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime принимает только aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Base(DeclarativeBase):
    pass


class Generation(Base):
    """Одна попытка получить аудио: вход, параметры, стадия, результат."""

    __tablename__ = "generations"
    __table_args__ = (
        CheckConstraint(f"status IN ({_quoted(STATUSES)})", name="ck_generations_status"),
        CheckConstraint(
            f"stage IS NULL OR stage IN ({_quoted(STAGES)})", name="ck_generations_stage"
        ),
        Index("ix_generations_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tts_provider: Mapped[str | None] = mapped_column(Text)
    voice: Mapped[str | None] = mapped_column(Text)
    music_tags: Mapped[str | None] = mapped_column(Text)
    music_seed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    stage: Mapped[str | None] = mapped_column(String(16))
    output_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    """Пара «ключ — значение»; значение хранится как JSON-текст."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


class GenerationFile(Base):
    """Файл результата генерации: один формат — одна строка."""

    __tablename__ = "generation_files"

    generation_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("generations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    format: Mapped[str] = mapped_column(String(8), primary_key=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
