"""Белый список пользовательских настроек: чтение, валидация, запись."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from ..assembly import normalize_formats
from ..assembly.base import UnknownFormatError
from ..paths import StorageDirError, expand, storage_dir
from ..storage import MISSING, get_setting, set_setting

SETTING_KEYS = (
    "output_dir",
    "tts_voice",
    "music_tags",
    "rate_percent",
    "pitch_hz",
    "growl",
    "output_formats",
)

MIN_RATE_PERCENT = -100
MAX_RATE_PERCENT = 200
MIN_PITCH_HZ = -100
MAX_PITCH_HZ = 100


class UnknownSettingError(ValueError):
    """Ключ вне белого списка."""


class InvalidSettingError(ValueError):
    """Значение не проходит валидацию."""

    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key


@dataclass(frozen=True)
class SettingsStore:
    """Действующие значения настроек поверх таблицы settings."""

    session_factory: sessionmaker[Session]
    default_music_tags: str
    default_formats: tuple[str, ...]
    default_output_dir: Path

    def read(self) -> dict[str, Any]:
        with self.session_factory() as session:
            return self._read(session)

    def update(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        validated = self._validate(payload)
        with self.session_factory() as session:
            for key, value in validated.items():
                set_setting(session, key, value)
            session.commit()
            return self._read(session)

    def _read(self, session: Session) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "output_dir": str(expand(self.default_output_dir)),
            "tts_voice": None,
            "music_tags": self.default_music_tags,
            "rate_percent": 0,
            "pitch_hz": 0,
            "growl": False,
            "output_formats": list(self.default_formats),
        }
        result: dict[str, Any] = {}
        for key in SETTING_KEYS:
            stored = get_setting(session, key, MISSING)
            result[key] = defaults[key] if stored is MISSING else stored
        return result

    def effective_output_dir(self) -> Path:
        return Path(self.read()["output_dir"])

    def _validate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        validated: dict[str, Any] = {}
        for key, value in payload.items():
            if key not in SETTING_KEYS:
                raise UnknownSettingError(f"неизвестная настройка: {key}")
            validated[key] = _validate_value(key, value)
        return validated


def _validate_value(key: str, value: Any) -> Any:
    if key == "output_dir":
        try:
            return str(storage_dir(value))
        except StorageDirError as exc:
            raise InvalidSettingError(key, str(exc)) from exc
    if key == "tts_voice":
        return _non_empty_string(key, value)
    if key == "music_tags":
        return _non_empty_string(key, value)
    if key == "rate_percent":
        return _int_between(key, value, MIN_RATE_PERCENT, MAX_RATE_PERCENT)
    if key == "pitch_hz":
        return _int_between(key, value, MIN_PITCH_HZ, MAX_PITCH_HZ)
    if key == "growl":
        if not isinstance(value, bool):
            raise InvalidSettingError(key, "ожидается true или false")
        return value
    if key == "output_formats":
        if not isinstance(value, list) or not value:
            raise InvalidSettingError(key, "нужен непустой список форматов")
        if not all(isinstance(item, str) for item in value):
            raise InvalidSettingError(key, "форматы должны быть строками")
        try:
            return list(normalize_formats(value))
        except UnknownFormatError as exc:
            raise InvalidSettingError(key, str(exc)) from exc
    raise UnknownSettingError(f"неизвестная настройка: {key}")


def _non_empty_string(key: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidSettingError(key, "ожидается непустая строка")
    return value.strip()


def _int_between(key: str, value: Any, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidSettingError(key, "ожидается целое число")
    if not minimum <= value <= maximum:
        raise InvalidSettingError(key, f"допустимо от {minimum} до {maximum}")
    return value
