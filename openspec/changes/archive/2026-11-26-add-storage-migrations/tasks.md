# Tasks

## 1. Зависимости и конфигурация

- [x] 1.1 Добавить `sqlalchemy>=2.0` и `alembic` в runtime-зависимости `pyproject.toml`; проверить `uv sync` и `uv run python -c "import sqlalchemy, alembic; print(sqlalchemy.__version__)"`
- [x] 1.2 Добавить в `Settings` поле `db_path` (`Path`, по умолчанию `data/muzifikator.sqlite3`, переменная `DB_PATH`); проверить, что `DB_PATH=/tmp/x.db` меняет значение, а по умолчанию путь относительный

## 2. Модели и миграции

- [x] 2.1 Реализовать `storage/models.py`: `Base`, `UTCDateTime`, `Generation` и `Setting` по схеме из design; проверить тестом, что `UTCDateTime` возвращает aware-UTC и одинаково сортирует записи
- [x] 2.2 Настроить Alembic: `alembic.ini` без URL, `migrations/env.py` с путём из `Settings` и метаданными моделей, offline-режим; проверить `uv run alembic upgrade head` на временном `DB_PATH` и наличие обеих таблиц в `sqlite3 .tables`
- [x] 2.3 Сгенерировать начальную ревизию и вычитать её руками (CHECK для `status` и `stage`, индекс по `created_at`); проверить `uv run alembic downgrade base` и повторный `upgrade head` на временной базе, затем `openspec`-независимую проверку: `uv run alembic current`

## 3. Инициализация хранилища

- [x] 3.1 Реализовать `storage/db.py`: `create_engine` с прагмами WAL/foreign_keys/busy_timeout, фабрику сессий и `init_storage(settings)` (каталог → движок → `upgrade head`) с `StorageError` при сбое; проверить тестами: пустой каталог создаётся, повторный вызов на той же базе не падает
- [x] 3.2 Подключить `init_storage` в `__main__.py` после preflight, до `uvicorn.run`, с сообщением в stderr и кодом 1 при `StorageError`; проверить тестом `main()` с подменённым `init_storage` (код 1) и запуском с `DB_PATH` в каталоге без прав на запись (код 1, порт не слушается)

## 4. Слой доступа: история

- [x] 4.1 Реализовать в `storage/repo.py` `create_generation`, `start_generation`, `set_stage`, `finish_generation`, `fail_generation`, `get_generation`, `list_generations` и `InvalidTransitionError`; проверить `pytest`-тестами на временной базе: создание со статусом `pending`, допустимые переходы, заполнение результата и ошибки
- [x] 4.2 Закрыть негативные случаи: недопустимый переход (`done → running`), изменение терминальной записи, `stage` у не-`running`, лимит и порядок в `list_generations`, неизвестный id → `None`; проверить тестами, что на каждое нарушение поднимается ожидаемая ошибка и данные не меняются
- [x] 4.3 Проверить сохранность: тест «перезапуск» — новый движок и сессия на том же файле видят ранее созданные записи без изменений

## 5. Слой доступа: настройки

- [x] 5.1 Реализовать `set_setting` и `get_setting` с JSON-сериализацией (`ensure_ascii=False`), `updated_at` и различием «нет ключа» / «сохранён `null`»; проверить тестами: вставка, замена, значение по умолчанию, отсутствие без default
- [x] 5.2 Проверить составные значения и независимость: объект, список, число, bool, `null` и кириллица проходят раунд-трип; добавление записи в историю не меняет настройки

## 6. Интеграционная проверка

- [x] 6.1 Прогнать `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`; все три без ошибок
- [x] 6.2 Сквозной запуск на чистом каталоге: удалить `data/`, запустить `uv run muzifikator`, убедиться по stderr, что миграции применены, `/api/health` отвечает `200`, `data/muzifikator.sqlite3` содержит `generations`, `settings`, `alembic_version`
- [x] 6.3 Повторный запуск на существующей базе с одной записью истории и одной настройкой: данные на месте, миграции не падают

## 7. Документация

- [x] 7.1 Добавить в `docs/operations.md` раздел про базу: путь, `DB_PATH`, ручные команды Alembic, предупреждение о копии файла перед обновлением, типовые ошибки; проверить, что команды выполняются как написано
- [x] 7.2 Обновить `docs/architecture.md`: хранилище в схеме компонентов и в разделе решений (авто-миграции, WAL, синхронный доступ); проверить рендер Mermaid
- [x] 7.3 Обновить `README.md`: упоминание `DB_PATH` в разделе настроек; проверить, что перечисленные переменные совпадают с `Settings`

## Workflow follow-up

- Провести ревью change вместе с владельцем и получить явное «approve plan».
- После реализации — «approve apply», коммит кода, затем архив: влить черновики `docs/capabilities/*.md` в `docs/capabilities/`, закрыть issue #2, обновить статус фазы 2 в `ROADMAP.md`.
