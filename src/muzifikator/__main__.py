"""Точка входа: настройки, логирование, preflight, хранилище, сервер."""

from __future__ import annotations

import logging
import sys

import uvicorn

from .app import create_app
from .assembly import AssemblyService
from .config import Settings
from .jobs import JobDeps, JobManager
from .logging_setup import configure_logging
from .music import MusicGenProvider, MusicService, TransformersBackend
from .preflight import format_failure, run_preflight
from .speech import EdgeTTSProvider, SpeechService
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

    session_factory = create_session_factory(engine)
    ffmpeg_bin = result.ffmpeg.path or "ffmpeg"
    ffprobe_bin = result.ffprobe.path or "ffprobe"

    speech = SpeechService(
        EdgeTTSProvider(),
        cache_dir=settings.tts_cache_dir,
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
        cache_limit_mib=settings.tts_cache_limit_mib,
    )
    music_backend = TransformersBackend(
        settings.musicgen_model,
        models_dir=settings.music_models_dir,
        device=settings.music_device,
    )
    music = MusicService(
        MusicGenProvider(music_backend),
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
        default_prompt=settings.music_prompt,
        model_name=settings.musicgen_model,
    )
    assembly = AssemblyService(
        ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin,
        output_dir=settings.output_dir,
        formats=settings.output_formats_list,
        min_duration_seconds=settings.music_min_duration_seconds,
    )
    jobs = JobManager(
        JobDeps(
            session_factory=session_factory,
            speech=speech,
            music=music,
            assembly=assembly,
            output_dir=settings.output_dir,
            tail_seconds=assembly.tail_seconds,
            formats=settings.output_formats_list,
        )
    )

    app = create_app(
        result,
        engine=engine,
        session_factory=session_factory,
        jobs=jobs,
        settings=settings,
    )
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
