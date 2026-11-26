# AGENTS

Правила работы в этом репозитории. Дополняют глобальные правила агента; при
конфликте действуют жёсткие ограничения `CONSTITUTION.md`.

## Гейты

- **Планирование**: артефакты change → сводка → явное «approve plan». После
  этого планирование заморожено до нового цикла.
- **Реализация**: только по «approve apply» для конкретного change.
- **Архивация**: только по «approve archive», после ревью/тестов.
- **Внешние записи**: Confluence и Jira запрещены (`CONSTITUTION.md` п. 2).
  Трекер — GitHub Issues; issue закрывается при архивации change.

## Коммиты и пуш

Цель — содержательные коммиты: отдельно решения, отдельно доставка.

- **approve plan** → коммит `docs(openspec): plan <phase> <change>` с каталогом
  `openspec/changes/<change>/` (proposal, integrations, specs, design, doc,
  tasks). Пуш не делается.
- **approve apply** → коммитов нет. Код, тесты и правки `docs/` копятся в
  рабочем дереве; их дифф — поверхность ревью.
- **approve archive** → два коммита подряд, в этом порядке:
  1. `feat: <итог фазы>` — код, тесты, `docs/`, `Refs #<issue>`;
  2. `chore(openspec): archive <change>` — синхронизация `openspec/specs`,
     перенос change в `openspec/changes/archive/`, `docs/capabilities/`,
     `ROADMAP.md` (статус фазы и номер issue), закрытый issue.
  Код-коммит создаётся до переноса change: так выполняется гейт «архив только
  после кода в целевой ветке».
- **Push** — только после пары коммитов архивации: `git push origin main`.
  Плановый коммит копится локально и уходит тем же пушем.

## Проверки перед архивными коммитами

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`.
- `openspec validate <change> --strict` и `openspec validate --specs` после
  синхронизации.
- Ручные сценарии из задач change выполнены, результат зафиксирован в ответе.

## Документация

- Формальные спеки — `openspec/specs/`; человекочитаемое — `docs/`.
- Capability-док вливается в `docs/capabilities/<capability>.md` при архивации.
- Диаграммы — Mermaid в код-фенсах; внешних публикаций нет.
