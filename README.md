# muzifikator

Вставляешь текст сообщения — получаешь аудио: текст озвучивается и накладывается на
сгенерированную инструментальную подложку (по умолчанию фолк-метал). Музыка генерится
локально, каждый раз новая, длительность подгоняется под речь.

## Требования

Нужны `ffmpeg` **и** `ffprobe` в `PATH`. Проверяются при старте: если чего-то нет,
приложение не запускается и просит поставить.

| Система | Установка |
|---|---|
| macOS | `brew install ffmpeg` |
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` (RPM Fusion) |
| Arch | `sudo pacman -S ffmpeg` |
| Windows | `winget install Gyan.FFmpeg`, либо `choco install ffmpeg`, либо `scoop install ffmpeg` |

При ручной установке берите сборку, где есть `ffprobe` (BtbN, gyan.dev), и добавьте
`bin` в `PATH`. Проверка:

```
ffmpeg -version
ffprobe -version
```

Опционально: `FFMPEG_BIN` и `FFPROBE_BIN` — пути к бинарям, если они лежат нестандартно.

## Стек

- Python 3.12, управление окружением — `uv`
- FastAPI + один статический HTML
- edge-tts (озвучка), MusicGen через `transformers` (музыка)
- ffmpeg (микс), SQLite + Alembic (история и настройки)

## Запуск

```
uv sync
uv run muzifikator
```

Сервис слушает `http://127.0.0.1:8000`; состояние:

```
curl -s http://127.0.0.1:8000/api/health
```

Настройки — переменными окружения `HOST`, `PORT`, `LOG_LEVEL`, `DB_PATH`,
`TTS_CACHE_DIR`, `TTS_CACHE_LIMIT_MIB`, `MUSICGEN_MODEL`, `MUSIC_MODELS_DIR`,
`MUSIC_PROMPT`, `MUSIC_DEVICE`, `OUTPUT_DIR`, `OUTPUT_FORMATS`, `FFMPEG_BIN`,
`FFPROBE_BIN` или локальным `.env`. База по умолчанию — `data/muzifikator.sqlite3`,
схема обновляется при старте; кэш озвучки — `.cache/tts`, ограничен 200 МиБ;
веса музыки — в `models/` (~2,2 ГБ, скачиваются при первом запуске); готовые
файлы — в `out/` (MP3 и M4A). Подробности, включая типовые ошибки, —
в `docs/operations.md`.

## Проверки

```
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Те же шаги выполняет GitHub Actions на каждый PR; подробности — в `docs/ci.md`.

## Интерфейс

Откройте `http://127.0.0.1:8000/`: текст, голос, теги музыки и папка результата,
прогресс по стадиям и список готовых файлов. Перегенерация делает новый трек с
новым seed, настройки голоса и тегов сохраняются.

## Генерация

```
curl -s -X POST localhost:8000/api/generations \
  -H 'content-type: application/json' \
  -d '{"text":"Текст сообщения","voice":"ru-RU-DmitryNeural"}'
curl -s localhost:8000/api/generations/<id>
```

Одна генерация одновременно; готовые файлы — в `out/`. Список файлов и
настройки — `GET /api/files` и `GET`/`PATCH /api/settings` (голос и теги можно
сохранить и не передавать в каждом запросе). Подробности и коды ошибок — в
`docs/operations.md`.

## Статус

Проект в разработке. План и задачи — в OpenSpec change.
