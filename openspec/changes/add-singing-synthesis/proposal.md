# Proposal

## Why

Оценка подтвердила: локальное русское пение возможно через NNSVS с готовой
моделью «Llane Crow» (CeVOX Cantano). Теперь пение должно стать основным
режимом: лирика и теги превращаются в песню — поющий вокал поверх
инструментальной подложки. Спящая речь остаётся запасным режимом `narrated`.

## What Changes

- Появляется локальный синтез русского пения: NNSVS с моделью «Llane Crow»,
  процедурная мелодия и русская графема-фонема (G2P); вход — лирика и теги,
  выход — вокал WAV.
- Появляется подложка: инструментальная музыка MusicGen по тегам и микс с
  вокалом (вокал главный, музыка фоном, нормализация громкости).
- Появляется режим задачи `song` (по умолчанию) и `narrated`; режим хранится в
  истории и выбирается в интерфейсе.
- В song-режиме голос TTS не используется: поёт фиксированный русский банк;
  MusicGen остаётся для подложки, а сборка — для микса и экспорта.
- Робот-пение (D) остаётся dev-инструментом в `tools/eval/`, результатом не
  является.

Явно вне скоупа: дообучение модели, выбор голоса в song, MIDI-вход, отдельный
вокал без подложки.

## Capabilities

### New Capabilities

- `singing-synthesis`: локальное русское пение по лирике и тегам (мелодия, G2P,
  NNSVS, вокал) с детерминизмом по seed.

### Modified Capabilities

- `generation-jobs`: добавляется режим задачи (`song`/`narrated`) и стадии
  `melody`/`sing`; `song` — по умолчанию.
- `generation-history`: колонка режима и запись параметров пения.
- `web-interface`: выбор режима; в song-режиме поле голоса не действует.

## Impact

- Код: новый подпакет `src/muzifikator/singing/` (мелодия, G2P, лейблы, NNSVS,
  сервис и микс); `jobs/pipeline.py` — ветка song; `jobs/schemas.py` — `mode`;
  `api/generations.py` и `web/` — выбор режима; миграция `mode` + расширение
  стадий.
- Зависимости: `nnsvs`, `utaupy`, `pyworld`, `soundfile` (runtime для song).
- Данные: веса NNSVS и банк в `models/` (вне репозитория); колонка
  `generations.mode`.
- Документация: `docs/capabilities/singing-synthesis.md`, обновление
  `generation-jobs.md`, `generation-history.md`, `web-interface.md`,
  `docs/operations.md`, `README.md`.
- Трекер: GitHub issue `tuch-ka/muzifikator#21`.
- Сеть: только Hugging Face за весами MusicGen (NNSVS-модель — GitHub release).
