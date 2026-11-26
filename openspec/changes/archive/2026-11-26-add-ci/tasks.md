# Tasks

## 1. Зависимости для CI

- [x] 1.1 Добавить в `pyproject.toml` индекс `pytorch-cpu` (`explicit = true`) и источник `torch` с маркером `sys_platform == 'linux'`; проверить `uv lock` без ошибок, наличие `download.pytorch.org/whl/cpu` в `uv.lock` для linux и `uv sync` на macOS без изменений
- [x] 1.2 Добавить `numpy` явной зависимостью и сделать импорты `torch`/`transformers` ленивыми в `music/backend.py` (`TYPE_CHECKING` для типов); проверить, что `uv run python -c "import muzifikator.music"` работает, а `uv run pytest -q` зелёный
- [x] 1.3 Проверить окружение без torch: `UV_PROJECT_ENVIRONMENT=.venv-lean uv sync --locked --no-install-package torch --no-install-package transformers`, затем `UV_PROJECT_ENVIRONMENT=.venv-lean uv run --no-sync pytest -q`; все тесты должны пройти, `.venv-lean` добавить в `.gitignore`
- [x] 1.4 Проверить, что `uv sync --locked` проходит локально (`--locked` не пересобирает lockfile); убедиться, что `uv run pytest -q` по-прежнему зелёный

## 2. Типизация (mypy)

- [x] 2.1 Добавить `mypy` dev-зависимостью и настройки `[tool.mypy]` (`files = ["src"]`, `strict = true`, `python_version = "3.12"`) с override `ignore_missing_imports` для `torch`/`transformers`; проверить, что `uv run mypy` запускается и показывает ошибки, а не падает на конфиге
- [x] 2.2 Исправить типизацию в `src/muzifikator` до чистого `uv run mypy`: аннотации, сужение `Any` на границе torch, отказ от неявных `Any` в протоколах и dataclass'ах; проверить нулевое число ошибок и отсутствие новых `type: ignore` без комментария-причины
- [x] 2.3 Проверить mypy в лёгком окружении без torch: `UV_PROJECT_ENVIRONMENT=.venv-lean uv run --no-sync mypy` — чисто, значит override работает; убедиться, что `uv run pytest -q` по-прежнему зелёный

## 3. Workflow: линт, типы, тесты

- [x] 3.1 Создать `.github/workflows/ci.yml`: триггеры `pull_request` в `main`, `push` в `main`, `workflow_dispatch`; job `checks` на `ubuntu-latest`, `timeout-minutes: 20`, `concurrency` с отменой предыдущего прогона, `permissions: contents: read`; проверить, что YAML парсится (`uv run python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"`)
- [x] 3.2 Добавить шаги: checkout, `astral-sh/setup-uv` с кэшем, `uv sync --locked --no-install-package torch --no-install-package transformers`, установка `ffmpeg` из apt с проверкой `ffmpeg -version` и `ffprobe -version`; проверить порядок команд локально в `.venv-lean`
- [x] 3.3 Добавить шаги `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`; проверить локально, что все четыре проходят на текущем коде

## 4. Workflow: спеки и сборка

- [x] 4.1 Добавить шаги `actions/setup-node` (Node 22) и `npm install -g @fission-ai/openspec@2.1.1`, затем `openspec validate --specs`; проверить команды локально. Дельты активных change в CI не проверяются: схема `taxmonitor` — внешний симлинк, на раннере недоступна (выяснено первым прогоном)
- [x] 4.2 Добавить шаг `uv build` и проверку установки: `uv venv .wheelcheck`, `uv pip install --python .wheelcheck/bin/python dist/*.whl`, импорт `muzifikator`; проверить локально, а `.wheelcheck` и `dist` добавить в `.gitignore`

## 5. Проверка workflow

- [x] 5.1 Проверить шаги локально целиком: `uv sync --locked`, apt-команды заменить проверкой наличия ffmpeg, затем линт, формат, mypy, тесты, спеки, сборка — всё без ошибок
- [x] 5.2 Запушить ветку фазы, открыть draft PR в `main` (событие `pull_request` подхватит workflow из ветки), дождаться зелёного прогона `CI`; при падении исправить, запушить и повторить. Это исключение из правила «пушим только на архиве», нужное, чтобы проверить сам CI; PR живёт до архива

## 6. Документация

- [x] 6.1 Перенести черновик `docs/ci.md` в репозиторий и добавить ссылку в `docs/README.md` (включая объяснение, почему CI не ставит torch, что mypy проверяет только `src` и что модельные тесты запускаются локально); проверить, что команды из документа выполняются как написано
- [x] 6.2 Добавить в `docs/operations.md` короткий раздел «Проверки перед PR» со ссылкой на `docs/ci.md` и напоминанием, что локально те же команды
- [x] 6.3 Обновить `README.md`: строка про CI и команда локальных проверок (включая `uv run mypy`); проверить, что названия шагов совпадают с workflow

## Workflow follow-up

- Владельцу включить branch protection для `main` с обязательной проверкой `checks` (шаги в `docs/ci.md`).
- После merge проверить, что `push` в `main` даёт зелёный прогон.
- Провести ревью change вместе с владельцем и получить явное «approve plan».
- После реализации — «approve apply», затем архив: перенести `docs/ci.md`, закрыть issue #5, обновить статус фазы 5 в `ROADMAP.md`.
