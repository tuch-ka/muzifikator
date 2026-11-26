"""Точка входа: настройки, логирование, preflight, хранилище, сервер."""

from __future__ import annotations

import logging
import sys

import uvicorn

from .app import create_app
from .config import Settings
from .logging_setup import configure_logging
from .preflight import format_failure, run_preflight
from .storage import StorageError, create_session_factory, init_storage

log = logging.getLogger("muzifikator")

_HELP = """\
muzifikator — озвучка текста поверх локально сгенерированной музыки.

Запуск:
  uv run muzifikator

Окружение:
  HOST, PORT, LOG_LEVEL, DB_PATH, FFMPEG_BIN, FFPROBE_BIN
  (значения можно положить в локальный .env)

Состояние сервиса:
  GET http://<HOST>:<PORT>/api/health
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help"}:
        print(_HELP)
        return 0

    settings = Settings()
    configure_logging(settings.log_level)
    log.info(
        "настройки: host=%s port=%s log_level=%s",
        settings.host,
        settings.port,
        settings.log_level,
    )

    result = run_preflight(settings)
    if not result.ok:
        print(format_failure(result), file=sys.stderr, flush=True)
        return 1

    try:
        engine = init_storage(settings)
    except StorageError as exc:
        print(
            f"Не удалось открыть хранилище {settings.db_path}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    app = create_app(
        result,
        engine=engine,
        session_factory=create_session_factory(engine),
    )
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
