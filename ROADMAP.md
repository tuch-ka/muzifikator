# Roadmap

История намерений. Здесь живут фазы до того, как они станут OpenSpec change.
Пока фаза не взята в работу, ни issue, ни change не создаются.

## Правило входа в работу

1. Берём следующую фазу из таблицы.
2. Создаём GitHub issue (одна фаза — один issue).
3. Создаём change с указанным именем; proposal ссылается на issue.
4. При архивации change закрываем issue и обновляем `docs/`.
5. Статус в таблице меняем здесь же, в том же коммите.

Issue не заводится заранее: он появляется вместе с проработкой идеи, а не
копится списком.

## Фазы

| # | Фаза | Change | Capabilities | Issue | Статус |
|---|---|---|---|---|---|
| 1 | Каркас: uv-проект, конфиг, логи, preflight ffmpeg/ffprobe, `/api/health` | `add-project-scaffold` | `ffmpeg-preflight`, `service-health` | #1 | done |
| 2 | Хранилище: SQLite, Alembic, таблицы `generations` и `settings` | `add-storage-migrations` | `generation-history`, `persisted-settings`, `storage-schema` | #2 | done |
| 3 | Озвучка: абстракция провайдера, edge-tts как первый, список голосов, длительность, кэш, «рык» | `add-tts` | `speech-synthesis` | — | planned |
| 4 | Музыка: MusicGen из transformers, seed, сегменты, теги | `add-music-generation` | `music-generation` | — | planned |
| 5 | Микс и экспорт: дакинг, фейды, mp3/m4a, имена файлов | `add-audio-mix` | `audio-assembly`, `output-files` | — | planned |
| 6 | Задачи: single-flight, стадии, polling, запись в БД | `add-job-orchestration` | `generation-jobs` | — | planned |
| 7 | API файлов и настроек: корни, листинг, сохранение настроек | `add-fs-and-settings-api` | `web-interface` | — | planned |
| 8 | UI: два поля, предзаполненные теги, перегенерация, папка, прогресс | `add-web-ui` | `web-interface` | — | planned |
| 9 | Провайдеры TTS: второй локальный провайдер (Piper), выбор провайдера в UI, ошибки провайдера | `add-tts-provider-switch` | `tts-providers` (new), `speech-synthesis` (mod), `web-interface` (mod) | — | planned |
| 10 | Тесты, README, лицензионные примечания | `add-tests-and-docs` | `skip_specs: true` | — | planned |

## Отложено до востребования

- Docker/контейнер: только если понадобится перенос на другую машину.
- CUDA-сборка torch: документируется одной строкой, extra не делаем.
- Автоматический fallback между провайдерами TTS: переключение пока ручное, через UI.
- Voice cloning (кастомные голоса из голосовых собеседника).
- Публикация `docs/` как сайта (MkDocs/Pages) — когда станет тесно в Markdown.
