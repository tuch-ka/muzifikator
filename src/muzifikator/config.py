"""Конфигурация приложения: значения по умолчанию, окружение, локальный .env."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_OUTPUT_FORMATS = ("mp3", "m4a")


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
    music_min_duration_seconds: float = Field(default=20.0, gt=0)
    music_device: Literal["auto", "mps", "cpu"] = "auto"
    output_dir: Path = Path("~/muzifikator")
    output_formats: str = "mp3,m4a"
    ffmpeg_bin: Path | None = None
    ffprobe_bin: Path | None = None

    @property
    def output_formats_list(self) -> tuple[str, ...]:
        return tuple(part for part in self.output_formats.split(",") if part)

    @field_validator("output_formats")
    @classmethod
    def _validate_output_formats(cls, value: str) -> str:
        parts = [part.strip().lower() for part in value.split(",") if part.strip()]
        unknown = sorted(set(parts) - set(SUPPORTED_OUTPUT_FORMATS))
        if unknown:
            raise ValueError(
                f"неизвестные форматы: {', '.join(unknown)}; "
                f"допустимы: {', '.join(SUPPORTED_OUTPUT_FORMATS)}"
            )
        if not parts:
            raise ValueError("нужен хотя бы один формат вывода")
        return ",".join(dict.fromkeys(parts))
