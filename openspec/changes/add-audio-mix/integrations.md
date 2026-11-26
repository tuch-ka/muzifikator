# Integrations

## Jira

- Skip. `CONSTITUTION.md` п. 2.2 запрещает Jira. Постоянное решение владельца;
  трекер — GitHub Issues (`CONSTITUTION.md` п. 2.3).

## Confluence

- Skip. `CONSTITUTION.md` п. 2.1 и 2.5 запрещают Confluence и внешние записи.
  Документация — `docs/`; черновики вливаются в
  `docs/capabilities/audio-assembly.md` и `docs/capabilities/output-files.md`
  при архивации.

## Human confirmations

- Владелец (`CONSTITUTION.md`, коммит `7fba070`): Jira и Confluence запрещены
  постоянно.
- Владелец, 2026-11-26: дакинг — sidechain-компрессор.
- Владелец, 2026-11-26: на выходе MP3 и M4A, оба по умолчанию.
- Владелец, 2026-11-26: после речи остаётся 2 секунды музыки с fade-out.
- Владелец, 2026-11-26: имена файлов — время плюс slug из текста.
- Владелец, 2026-11-26: slug транслитерируется в латиницу, кириллица в именах
  файлов не остаётся.
- Владелец, 2026-11-26: наличие AAC (и MP3) энкодеров проверяется preflight;
  сторонние сборки ffmpeg как зависимость не поставляются — `CONSTITUTION.md`
  п. 2.4 ограничивает источники сети.
