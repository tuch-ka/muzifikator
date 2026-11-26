# Design

## Context

См. `proposal.md` — Why. Каркас (фаза 1) даёт `Settings` на `pydantic-settings`,
логирование в stderr, preflight и `create_app(preflight)`; хранилища нет. Путь
`data/` уже в `.gitignore`, каталог не создаётся. Владелец выбрал SQLAlchemy 2.0
ORM, статус и стадию в `generations` сразу и авто-миграции при старте.

## Goals / Non-Goals

**Goals:**

- Схема, из которой фазы 3–6 пишут данные без переделки: параметры, статус,
  стадия, результат, ошибка.
- Отсутствие ручных шагов: пустая машина → `uv sync` → `uv run muzifikator`
  получает рабочую базу.
- Тестируемость без HTTP: слой доступа проверяется на временной базе.

**Non-Goals:**

- HTTP-эндпоинты истории и настроек (фазы 7–8), очередь и стадии пайплайна
  (фаза 6).
- Миграция существующих данных: базы ещё не существует ни у кого.
- Асинхронный доступ (`aiosqlite`, async SQLAlchemy): запросы редкие, объём
  единичный, синхронный слой проще.

## Decisions

### 1. Зависимости

`sqlalchemy>=2.0`, `alembic` — **runtime**, а не dev: миграции применяются
самим приложением при старте, значит Alembic нужен и в рабочем окружении.

Альтернатива: держать Alembic в dev и требовать ручной `alembic upgrade` —
противоречит выбору владельца и создаёт шаг, который забывают.

### 2. Раскладка

```
src/muzifikator/storage/__init__.py
src/muzifikator/storage/db.py        # движок, сессии, инициализация
src/muzifikator/storage/models.py    # Base, Generation, Setting, UTCDateTime
src/muzifikator/storage/repo.py      # операции чтения/записи
alembic.ini
migrations/env.py
migrations/versions/<rev>_initial_schema.py
```

Альтернатива: один `storage.py` — на две таблицы и ~8 функций файл перестаёт
быть обозримым к фазе 6.

### 3. Схема

`generations`:

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | TEXT | PK, uuid4 hex |
| `created_at` | DATETIME (UTC) | NOT NULL, индекс по убыванию |
| `finished_at` | DATETIME (UTC) | NULL |
| `text` | TEXT | NOT NULL |
| `tts_provider` | TEXT | NULL |
| `voice` | TEXT | NULL |
| `music_tags` | TEXT | NULL |
| `music_seed` | INTEGER | NULL |
| `status` | TEXT | NOT NULL, CHECK в `pending`,`running`,`done`,`failed`, default `pending` |
| `stage` | TEXT | NULL, CHECK в `tts`,`music`,`mix` |
| `output_path` | TEXT | NULL |
| `duration_seconds` | REAL | NULL |
| `error` | TEXT | NULL |

`settings`: `key` TEXT PK, `value` TEXT NOT NULL (JSON), `updated_at`
DATETIME NOT NULL.

Статус и стадия — TEXT с CHECK, а не SQLAlchemy `Enum`: в SQLite `Enum`
превращается в VARCHAR+CHECK, но при правке набора значений Alembic
генерирует пересоздание таблицы. CHECK остаётся дополнительной страховкой,
основная валидация — в коде.

Параметры озвучки и музыки — отдельные колонки, а не JSON-блок: их будут
фильтровать и показывать в истории. JSON остаётся только у `settings.value`,
где набор ключей заранее неизвестен.

### 4. Время в UTC

`UTCDateTime` — `TypeDecorator` над `DateTime`: пишет наивное UTC, читает
aware-UTC. Без этого SQLite теряет смещение, а сортировка истории и «время
завершения» начинают зависеть от часового пояса машины.

Альтернатива: `DateTime(timezone=True)` как есть — SQLite возвращает наивное
значение, и каждый вызывающий код гадает о зоне.

### 5. Движок и сессии

`create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})`,
`sessionmaker(bind=engine, expire_on_commit=False)`.
На подключении: `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`,
`PRAGMA busy_timeout=5000`.

WAL — потому что фаза 6 читает статус на polling, пока пишется результат;
`busy_timeout` гасит редкие `database is locked` без ретраев в коде.
`check_same_thread=False` нужен, потому что FastAPI выполняет синхронные
обработчики в пуле потоков.

### 6. Миграции

`migrations/env.py` берёт URL из `Settings().db_path`, а не из `alembic.ini`
(в `alembic.ini` URL пустой): единственный источник правды — конфигурация
приложения. Начальная ревизия генерируется `alembic revision --autogenerate`
против пустой базы и затем вычитывается руками — autogenerate не ловит CHECK
и порядок индексов.

`init_storage(settings)` = создать каталог → создать движок → `alembic upgrade
head`. Вызывается в `main()` после preflight и до `uvicorn.run`; ошибка любого
шага печатается и приводит к коду 1 (как у preflight). Порядок: ffmpeg-проверка
дешевле и чаще ломается, поэтому идёт первой.

Альтернатива: `Base.metadata.create_all()` при старте — быстро, но схема и
миграции расходятся, и первая же колонка, добавленная в фазе 6, ломает старые
базы. `create_all` не используется нигде, включая тесты: тесты гоняют те же
миграции.

### 7. Слой доступа

Функции в `repo.py` принимают `Session`, возвращают ORM-объекты и ничего не
коммитят: коммит — на вызывающей стороне, чтобы фаза 6 могла объединять
несколько изменений в одну транзакцию.

Набор: `create_generation`, `start_generation`, `set_stage`,
`finish_generation`, `fail_generation`, `get_generation`, `list_generations`,
`get_setting`, `set_setting`.

Недопустимый переход (например, `done → running`) поднимает
`InvalidTransitionError` из `storage`. Терминальные статусы `done` и `failed`
не меняются. `stage` допускается только у `running`.

Настройки: `set_setting(session, key, value)` сериализует значение
`json.dumps(ensure_ascii=False)`; `get_setting(session, key, default=_MISSING)`
возвращает `default` (в том числе `None`), если ключа нет. Отсутствие ключа и
сохранённый `null` различимы.

### 8. Проверка

`pytest` на временной базе (`tmp_path`, миграции реальные):
создание и чтение истории, порядок и лимит, неизвестный id, все переходы
статусов и отказ на недопустимом, JSON-раунд-трип настроек (объект, список,
число, `null`) и независимость от истории, повторный `upgrade head` на
заполненной базе, «перезапуск» через новый движок на том же файле.
Негативный сценарий недоступной базы — тест `init_storage` на каталоге без
прав и тест `main()` с подменённым `init_storage`, что код возврата 1.

## Risks / Trade-offs

- Авто-миграции при старте: неудачная миграция блокирует запуск → это и есть
  требуемое поведение; откат — восстановить файл базы из копии, поэтому в
  `docs/operations.md` фиксируется «база — ценный файл, копируется перед
  обновлением».
- WAL создаёт рядом `-wal` и `-shm` → они попадают в `data/`, уже
  игнорируемый; ничего дополнительно не настраивается.
- `check_same_thread=False` допускает конкурентные записи из пула потоков →
  риск `database is locked` гасится WAL и `busy_timeout`; одна генерация
  одновременно (фаза 6) делает конфликт маловероятным.
- Alembic в runtime увеличивает окружение на один пакет → приемлемо ради
  отсутствия ручного шага.
- CHECK-ограничения в SQLite требуют пересоздания таблицы при изменении
  набора значений → поэтому набор статусов фиксируется сразу с запасом под
  фазу 6, а не правится по одному значению.
- `UTCDateTime` — собственный тип, его надо помнить при новых колонках →
  правило в `docs/capabilities/storage-schema.md`.

## Migration Plan

Существующих баз нет: первый запуск создаёт файл и применяет начальную
ревизию. Откат в разработке — удалить `data/muzifikator.sqlite3*`; откат кода —
revert коммита фазы. Порядок выката: `uv sync` → `uv run muzifikator`
(миграция выполняется автоматически) → проверить старт и отсутствие ошибок в
stderr.

## Open Questions

Нет: лимит истории по умолчанию (50) и набор статусов/стадий выбраны с запасом
под фазы 3–6 и меняются одной миграцией.
