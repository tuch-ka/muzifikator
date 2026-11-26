# Vendor: NNSVS + SimpleEnunu (MIT)

Снимок для headless-синтеза пения. Источники:

- `nnsvs/`, `utils/` — NNSVS dev (MIT), снимок из релиза
  `rokujyushi/SimpleEnunu` (SimpleEnunuServer-0.2.0+0.local.9.1).
- `enulib/`, `enunu_steps.py` — SimpleEnunu (MIT), тот же релиз.

В `enunu_steps.py` внесены патчи под нашу версию окружения:
1. `SimpleEnunuServer(..., temp_dir=...)` — недостающий позиционный аргумент.
2. `set_paths(temp_dir=...)` без `songname`.
3. `segmented_synthesis=False` (на коротких фразах segment_labels падает).
4. Удалён `import colored_traceback.always` — в non-TTY падает curses.setupterm.

Ещё два патча выполняются в рантайме (`singing/nnsvs.py`):
`os.startfile` shim (macOS) и обёртка `torch.load(weights_only=False)`.
