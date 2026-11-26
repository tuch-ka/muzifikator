"""Модели API задач."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class GenerationCreate(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = Field(default=None, min_length=1)
    rate_percent: int | None = Field(default=None, ge=-100, le=200)
    pitch_hz: int | None = Field(default=None, ge=-100, le=100)
    growl: bool | None = None
    music_tags: str | None = None
    music_seed: int | None = Field(default=None, ge=0)
    formats: list[str] | None = None
    folder: str | None = None

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("текст не может быть пустым")
        return value


class GenerationCreated(BaseModel):
    id: str
    status: str


class GenerationView(BaseModel):
    id: str
    status: str
    stage: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    error: str | None = None
    files: dict[str, str] = Field(default_factory=dict)


class VoiceView(BaseModel):
    name: str
    locale: str
    gender: str
