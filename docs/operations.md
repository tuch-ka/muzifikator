# Запуск и окружение

Запуск, окружение, установка ffmpeg, типовые ошибки.

## Что нужно

- Python 3.12 и `uv` (управление окружением и зависимостями).
- `ffmpeg` и `ffprobe` в `PATH` либо явно указанные пути.

## Установка инструментов

| Инструмент | macOS | Debian / Ubuntu | Fedora |
|---|---|---|---|
| ffmpeg (+ ffprobe) | `brew install ffmpeg` | `sudo apt install ffmpeg` | `sudo dnf install ffmpeg` (RPM Fusion) |
| uv | `brew install uv` | по явному разрешению владельца | по явному разрешению владельца |

`uv` ставится из Homebrew: другие способы установки тянут пакеты из источников,
не перечисленных в `CONSTITUTION.md` п. 2.4, и требуют отдельного разрешения
владельца.

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
| `DB_PATH` | `data/muzifikator.sqlite3` | Файл базы SQLite; каталог создаётся при старте |
| `FFMPEG_BIN` | не задана | Явный путь к `ffmpeg` (приоритет над `PATH`) |
| `FFPROBE_BIN` | не задана | Явный путь к `ffprobe` |

Значения можно положить в локальный `.env` в корне репозитория; файл в
`.gitignore` и не коммитится.

## Запуск

```
uv sync
uv run muzifikator
```

Эквивалент: `uv run python -m muzifikator`. `uv sync` ставит и dev-инструменты
(`pytest`, `ruff`); для проверок — `uv run pytest`, `uv run ruff check .`.

Успешный старт: в stderr строки preflight с путями и версиями бинарей, строки
хранилища о применённых миграциях, затем сообщение uvicorn о том, что сервис
слушает адрес. Проверка:

```
curl -s http://127.0.0.1:8000/api/health
```

## База данных

База — файл SQLite по умолчанию `data/muzifikator.sqlite3`; каталог создаётся
автоматически. Схема приводится к последней ревизии при каждом старте, ручные
команды не нужны.

Ручные команды для разработки:

```
uv run alembic upgrade head                    # применить миграции
uv run alembic downgrade -1                    # откатить одну ревизию
uv run alembic revision --autogenerate -m "…"  # заготовка новой миграции
uv run alembic current                          # текущая ревизия
```

`DB_PATH=/tmp/other.sqlite3 uv run alembic ...` работает: путь берётся из той же
конфигурации, что и приложением.

**База — ценный файл.** Перед обновлением приложения её стоит скопировать:
`cp data/muzifikator.sqlite3 data/muzifikator.sqlite3.bak`. Неудачная миграция
блокирует запуск, но не должна стоить истории. Копировать нужно на остановленном
сервисе (или вместе с файлами `-wal` и `-shm`).

Посмотреть содержимое:

```
sqlite3 data/muzifikator.sqlite3 '.tables'
sqlite3 data/muzifikator.sqlite3 'select id, status, stage, created_at from generations order by created_at desc limit 10;'
sqlite3 data/muzifikator.sqlite3 'select key, value from settings;'
```

## Типовые проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| Процесс завершился с кодом 1, в выводе «не найден ffprobe» | Сборка ffmpeg без `ffprobe` | Поставить сборку с `ffprobe` |
| Процесс завершился, в выводе «путь из настроек не найден» | `FFMPEG_BIN`/`FFPROBE_BIN` указывает на несуществующий файл | Исправить путь или убрать переменную |
| `ffmpeg -version` работает в терминале, а preflight не находит | Разный `PATH` у терминала и у процесса (IDE, launchd) | Запускать из того же окружения или задать `FFMPEG_BIN` |
| `connection refused` на `/api/health` | Сервис не запущен | Смотреть stderr, причина отказа preflight там |
| `version: null` в health | Нестандартный формат вывода сборки | Не ошибка; проверить `ffmpeg -version` руками |
| Процесс завершился с кодом 1, в выводе «Не удалось открыть хранилище» | Нет прав на каталог, диск полон, миграция падает | Проверить права на `data/`, место на диске, текст ошибки миграции |
| `database is locked` | Второй экземпляр приложения на той же базе | Остановить лишний процесс; один файл — один сервис |

## Каталоги

`models/`, `data/`, `logs/`, `.cache/`, `out/`, `.tools/` — вне репозитория
(`.gitignore`). `data/` создаётся при первом старте вместе с файлом базы; в
WAL-режиме рядом появляются `-wal` и `-shm`. Остальные каталоги появляются
вместе с фазами, которым они нужны.
