# Архитектура

Черновик. Описывает плановую архитектуру; обновляется при архивации каждого
change, который меняет компоненты, потоки или зависимости.

## Компоненты

```mermaid
flowchart LR
    UI["Web UI<br/>static HTML + JS"] --> API["FastAPI"]
    API --> JOB["JobManager<br/>single-flight"]
    JOB --> TTS["edge-tts"]
    JOB --> MUS["MusicGen<br/>transformers"]
    JOB --> MIX["ffmpeg<br/>mix, ducking, fades"]
    MIX --> OUT["выходной каталог<br/>файловая система"]
    API --> DB[("SQLite<br/>generations, settings")]
    MUS --> MODELS[("models/")]
    TTS --> CACHE[(".cache/tts")]
```

## Поток генерации

```mermaid
sequenceDiagram
    participant U as UI
    participant A as API
    participant J as JobManager
    participant T as TTS
    participant M as MusicGen
    participant F as ffmpeg

    U->>A: POST /api/jobs
    A->>J: создать задачу
    J->>T: синтез (или кэш по хэшу)
    T-->>J: голос + длительность
    J->>M: сегменты под длительность
    M-->>J: музыка
    J->>F: микс (дакинг, фейды, нормализация)
    F-->>J: готовый файл
    J-->>A: завершено
    U->>A: GET /api/jobs/{id}
```

## Решения и ограничения

- Одна модель MusicGen в памяти, одна генерация одновременно.
- Окно модели — 30 с; длиннее — сегменты с кроссфейдом.
- На MPS считается в `float32`; CPU-режим возможен, но медленный.
- TTS-кэш по хэшу текста: перегенерация музыки не переозвучивает.
- Документация и спецификации — в репозитории; внешних систем нет.

## Что обновлять при изменениях

- Новый компонент или зависимость → схема выше и раздел «Решения».
- Изменение потока → sequence-диаграмма.
- Изменение формата файлов или каталогов → раздел в `operations.md`.
