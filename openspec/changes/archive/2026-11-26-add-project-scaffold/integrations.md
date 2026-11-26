# Integrations

## Jira

- Skip. `CONSTITUTION.md` п. 2.2 запрещает Jira: никаких тикетов, переходов,
  комментариев и упоминаний. Это постоянное решение владельца, отдельного
  подтверждения на change не требуется. Трекер — GitHub Issues (`CONSTITUTION.md`
  п. 2.3).

## Confluence

- Skip. `CONSTITUTION.md` п. 2.1 и 2.5 запрещают Confluence и любые внешние
  записи: страницы, комментарии, ссылки, макросы. Человекочитаемая документация
  живёт в `docs/` этого репозитория (`CONSTITUTION.md` п. 3.1), черновик change
  вливается в `docs/capabilities/<capability>.md` при архивации.

## Human confirmations

- Владелец (`CONSTITUTION.md`, коммит `7fba070`): Jira и Confluence запрещены в
  проекте постоянно, external writes отсутствуют.
- Владелец, 2026-11-25, при проработке `add-project-scaffold`: `/api/health`
  выделяется в отдельную capability `service-health`, а не входит в
  `ffmpeg-preflight`.
- Владелец, 2026-11-25: `gh` установлен и авторизован (аккаунт `tuch-ka`),
  GitHub issue фазы создан — `tuch-ka/muzifikator#1`; номер подставлен в
  `proposal.md`.
