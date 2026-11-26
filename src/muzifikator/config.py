"""Конфигурация приложения: значения по умолчанию, окружение, локальный .env."""

from pathlib import Path

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
    ffmpeg_bin: Path | None = None
    ffprobe_bin: Path | None = None
