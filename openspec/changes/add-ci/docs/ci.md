# CI: проверки в GitHub Actions

> Черновик фазы «CI» (`add-ci`). При архивации change переносится в `docs/ci.md`.

## Что проверяется

Один workflow `CI` (`.github/workflows/ci.yml`) на `ubuntu-latest`:

| Шаг | Команда | Что ловит |
|---|---|---|
| Линт | `uv run ruff check .` | ошибки стиля и импортов |
| Формат | `uv run ruff format --check .` | неотформатированный код |
| Типы | `uv run mypy` | ошибки типизации в `src/muzifikator` |
| Тесты | `uv run pytest` | регрессии; `network` и `model` исключены |
| Спеки | `openspec validate --specs` | ошибки в основных спеках |
| Сборка | `uv build` + установка wheel в отдельное окружение | пакет не собирается или не импортируется |

Запускается на `pull_request` в `main`, на `push` в `main` и вручную
(`workflow_dispatch`).

## Как повторить локально

```
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
openspec validate --specs
uv build
```

`uv run pytest` по умолчанию не запускает маркеры `network` и `model`: они требуют
сети и весов и в CI не идут. Вручную: `uv run pytest -m network` или `-m model`.

## Чего в CI нет

- Модельных и сетевых тестов: веса ~2,2 ГБ и минуты времени.
- Проверки типов тестов: `mypy` настроен только на `src/muzifikator`.
- Валидации дельт активных change: схема `taxmonitor` подключена симлинком из
  внешнего стора (`CONSTITUTION.md` п. 6.1) и на раннере недоступна. Дельты
  проверяются локально и на `openspec archive`.
- Типов `torch`/`transformers`: пакеты в CI не установлены, для них включён
  `ignore_missing_imports`; вызовы модели типизируются как `Any` внутри
  `music/backend.py`.
- Матрицы Python и ОС: проект живёт на Python 3.12 и macOS/ubuntu.
- Публикации артефактов, релизов, CD.

## Особенности

- CI не устанавливает `torch` и `transformers` (`uv sync --locked
  --no-install-package ...`): тестам они не нужны, модельные тесты исключены
  маркером. Слой музыки импортирует их лениво, поэтому импорт пакета и юнит-тесты
  проходят без них.
- Полная установка на Linux берёт `torch` из CPU-индекса PyTorch
  (`pyproject.toml`), чтобы не тянуть CUDA-зависимости; на macOS установка не
  меняется.
- Модельные тесты (`uv run pytest -m model`) выполняются только локально: они
  скачивают веса и считают на устройстве.
- `ffmpeg` ставится из apt перед тестами; версии проверяются сразу после
  установки.
- OpenSpec CLI ставится из npm версией `@fission-ai/openspec@2.1.1`;
  обновлять её нужно вместе с локальной версией.
- Установка идёт `uv sync --locked`: расхождение `uv.lock` и `pyproject.toml`
  роняет прогон, а не пересобирает lockfile молча.

## Настройки репозитория (владелец)

Чтобы CI реально блокировал merge:

1. Settings → Branches → Add branch protection rule для `main`.
2. Включить «Require status checks to pass before merging» и выбрать `checks`.
3. Включить «Require branches to be up to date before merging».
4. Прямой push в `main` не нужен: весь код идёт через PR.

## Диагностика

- Упавший шаг: Actions → нужный run → шаг; логи доступны без скачивания.
- Расхождение lockfile: локально `uv lock`, закоммитить `uv.lock`.
- Упала валидация спек: `openspec validate --specs` локально; дельты активных
  change проверяются отдельно — `openspec validate <change> --strict` (в CI они
  не проверяются, см. выше).
- «Не собирается wheel»: `uv build` локально; чаще это забытый новый модуль в
  пакете или ошибка импорта на верхнем уровне.
- Ручной прогон после merge: `gh workflow run ci.yml` и `gh run watch`.
  До merge `workflow_dispatch` недоступен: GitHub требует, чтобы файл workflow
  был на default-ветке.
