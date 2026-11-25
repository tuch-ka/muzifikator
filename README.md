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

## Статус

Проект в разработке. План и задачи — в OpenSpec change.
