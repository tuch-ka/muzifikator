"""Конфигурация приложения: значения по умолчанию, окружение, локальный .env."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки процесса. Имена переменных окружения совпадают с именами полей."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    db_path: Path = Path("data/muzifikator.sqlite3")
    tts_cache_dir: Path = Path(".cache/tts")
    tts_cache_limit_mib: int = Field(default=200, ge=0)
    musicgen_model: str = "facebook/musicgen-small"
    music_models_dir: Path = Path("models")
    music_prompt: str = "folk metal"
    music_device: Literal["auto", "mps", "cpu"] = "auto"
    ffmpeg_bin: Path | None = None
    ffprobe_bin: Path | None = None
