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

## Ветки

- Один change — одна ветка, создаётся от `main` при «approve plan».
- Имя ветки: `MUZ-<issue>-<change>`, например `MUZ-4-add-music-generation`.
- `MUZ-<N>` — локальный ключ задачи, где `N` — номер GitHub issue. Это не Jira:
  Jira в проекте запрещена (`CONSTITUTION.md` п. 2.2). Ключ выводится из issue
  механически, отдельного реестра нет.
- Прямо в `main` попадает только merge ветки и исключение из раздела коммитов.

## Коммиты и пуш

Цель — содержательные коммиты: отдельно решения, отдельно доставка. Каждый
коммит change начинается с ключа задачи: `MUZ-<issue>: <тип>: <итог>`.

- **approve plan** → в ветке коммит
  `MUZ-<issue>: docs(openspec): plan <phase> <change>` с каталогом
  `openspec/changes/<change>/` (proposal, integrations, specs, design, doc,
  tasks). Пуш не делается.
- **approve apply** → коммитов нет. Код, тесты и правки `docs/` копятся в
  рабочем дереве; их дифф — поверхность ревью.
- **approve archive** → два коммита подряд, в этом порядке:
  1. `MUZ-<issue>: feat: <итог фазы>` — код, тесты, `docs/`, `Refs #<issue>`;
  2. `MUZ-<issue>: chore(openspec): archive <change>` — синхронизация
     `openspec/specs`, перенос change в `openspec/changes/archive/`,
     `docs/capabilities/`, `ROADMAP.md` (статус фазы и номер issue), закрытый
     issue.
  Код-коммит создаётся до переноса change: так выполняется гейт «архив только
  после кода изменён».
- **Merge и push** — только после пары архивных коммитов:
  1. `git push -u origin MUZ-<issue>-<change>`;
  2. `git switch main` → `git merge --no-ff MUZ-<issue>-<change>`;
     merge-коммит: `MUZ-<issue>: merge <change>`;
  3. `git push origin main`;
  4. `git branch -d MUZ-<issue>-<change>` (локально и в origin).
- **`Closes #<issue>` в коммитах не использовать**: GitHub закрыл бы issue при
  merge, а по процессу issue закрывается на архивации. В коде — `Refs #<issue>`.
- **Исключение — коммиты без change**: правки процесса, `docs/`, README-опечатки,
  инфраструктура. Они идут прямо в `main`, без ключа, с обычным типом
  (`docs:`, `chore:`).

## Проверки перед архивными коммитами

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`.
- `openspec validate <change> --strict` и `openspec validate --specs` после
  синхронизации.
- Ручные сценарии из задач change выполнены, результат зафиксирован в ответе.

## Документация

- Формальные спеки — `openspec/specs/`; человекочитаемое — `docs/`.
- Capability-док вливается в `docs/capabilities/<capability>.md` при архивации.
- Диаграммы — Mermaid в код-фенсах; внешних публикаций нет.
