# Integrations

## Jira

- Skip. `CONSTITUTION.md` п. 2.2 запрещает Jira. Постоянное решение владельца;
  трекер — GitHub Issues (`CONSTITUTION.md` п. 2.3). GitHub Actions — не
  внешняя система учёта, а проверка в том же репозитории.

## Confluence

- Skip. `CONSTITUTION.md` п. 2.1 и 2.5 запрещают Confluence и внешние записи.
  Документация — `docs/ci.md` в этом репозитории.

## Human confirmations

- Владелец (`CONSTITUTION.md`, коммит `7fba070`): Jira и Confluence запрещены
  постоянно.
- Владелец, 2026-11-26: проверки CI — ruff, pytest, openspec validate и `uv
  build` с проверкой установки.
- Владелец, 2026-11-26: триггеры — `pull_request` в `main` и `push` в `main`.
- Владелец, 2026-11-26: `torch` на Linux ставится из CPU-индекса PyTorch.
- Владелец, 2026-11-26: фаза 5 — это CI; она вставлена в `ROADMAP.md` перед
  миксом, остальные фазы переномерованы.
