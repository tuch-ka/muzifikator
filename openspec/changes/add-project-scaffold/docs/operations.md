# Запуск и окружение

> Черновик фазы «Каркас» (`add-project-scaffold`). При архивации change
> семантически вливается в `docs/operations.md`.

## Что нужно

- Python 3.12 и `uv` (управление окружением и зависимостями).
- `ffmpeg` и `ffprobe` в `PATH` либо явно указанные пути.

## Установка инструментов

| Инструмент | macOS | Debian / Ubuntu | Fedora |
|---|---|---|---|
| ffmpeg (+ ffprobe) | `brew install ffmpeg` | `sudo apt install ffmpeg` | `sudo dnf install ffmpeg` (RPM Fusion) |
| uv | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

Проверка:

```
uv --version
ffmpeg -version
ffprobe -version
```

Важно: некоторые сборки ffmpeg идут без `ffprobe`. Нужна сборка, где он есть
(BtbN, gyan.dev для Windows).

## Переменные окружения

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `HOST` | `127.0.0.1` | Адрес прослушивания |
| `PORT` | `8000` | Порт |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `FFMPEG_BIN` | не задана | Явный путь к `ffmpeg` (приоритет над `PATH`) |
| `FFPROBE_BIN` | не задана | Явный путь к `ffprobe` |

Значения можно положить в локальный `.env` в корне репозитория; файл в
`.gitignore` и не коммитится.

## Запуск

```
uv sync
uv run muzifikator
```

Эквивалент: `uv run python -m muzifikator`.

Успешный старт: в stderr строки preflight с путями и версиями бинарей, затем
сообщение uvicorn о том, что сервис слушает адрес. Проверка:

```
curl -s http://127.0.0.1:8000/api/health
```

## Типовые проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| Процесс завершился с кодом 1, в выводе «не найден ffprobe» | Сборка ffmpeg без `ffprobe` | Поставить сборку с `ffprobe` |
| Процесс завершился, в выводе «путь из настроек не найден» | `FFMPEG_BIN`/`FFPROBE_BIN` указывает на несуществующий файл | Исправить путь или убрать переменную |
| `ffmpeg -version` работает в терминале, а preflight не находит | Разный `PATH` у терминала и у процесса (IDE, launchd) | Запускать из того же окружения или задать `FFMPEG_BIN` |
| `connection refused` на `/api/health` | Сервис не запущен | Смотреть stderr, причина отказа preflight там |
| `version: null` в health | Нестандартный формат вывода сборки | Не ошибка; проверить `ffmpeg -version` руками |

## Каталоги

`models/`, `data/`, `logs/`, `.cache/`, `out/`, `.tools/` — вне репозитория
(`.gitignore`). Каркас их не создаёт; каталоги появляются вместе с фазами,
которым они нужны.
