"""HTTP-слой: роутеры задач, файлов и настроек."""

from .generations import build_generations_router
from .library import (
    FileEntry,
    FilePage,
    build_library_router,
    media_type,
    reveal_command,
)
from .settings import build_settings_router
from .settings_store import (
    SETTING_KEYS,
    InvalidSettingError,
    SettingsStore,
    UnknownSettingError,
)
from .ui import build_ui_router, web_directory

__all__ = [
    "SETTING_KEYS",
    "FileEntry",
    "FilePage",
    "InvalidSettingError",
    "SettingsStore",
    "UnknownSettingError",
    "build_generations_router",
    "build_library_router",
    "build_settings_router",
    "build_ui_router",
    "media_type",
    "reveal_command",
    "web_directory",
]
