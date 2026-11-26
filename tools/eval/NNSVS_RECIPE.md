# Рецепт headless-синтеза NNSVS (Llane Crow)

Проверено 2026-11-26 на macOS (M4 Pro). Модель: `models/nnsvs/llane_crow/`
(релиз `SCERYP/russian_nnsvs_llane_crow_db_vb`, внутри готовая модель CeVOX
Cantano: acoustic/duration/timelag `.pth` + hed + dic + enuconfig.yaml).

## Источники

- SimpleEnunu release `SimpleEnunuServer-0.2.0+0.local.9.1.zip` — содержит
  `nnsvs-master/` (dev-версия NNSVS с `nnsvs.svs.SPSVS` и `utils/enunu2nnsvs`),
  `enunu_steps.py`, `enulib/`. Pip-пакет `nnsvs` 0.1.1 НЕ подходит: в нём нет
  `nnsvs.svs`.

## Окружение (отдельный venv, не основной)

```
uv venv .venv-nnsvs
uv pip install --python .venv-nnsvs/bin/python \
  numpy==1.26.4 torch omegaconf pyyaml tqdm utaupy nnmnkwii scipy \
  scikit-learn pyworld hydra-core "matplotlib<3.9" "setuptools<81" \
  colored_traceback h5py librosa pyloudnorm
```

`numpy<2` обязателен: в nnsvs-master `int(array[0])` ломается на numpy 2.x.

## Патчи (4)

1. `os.startfile` нет на macOS → `os.startfile = lambda p: None`.
2. `torch.load` в nnsvs-master вызывает без `weights_only` → обёртка
   `weights_only=False` (модель содержит omegaconf-глобалы).
3. `enunu_steps.py`: вызов `SimpleEnunuServer(model_dir, device=...)` →
   добавить `temp_dir=temp_dir` (сигнатура класса требует его позиционным).
4. `enunu_steps.py`: `engine.set_paths(temp_dir=..., songname=...)` →
   убрать `songname` (метод принимает только `temp_dir`).
5. `enunu_steps.py`: `segmented_synthesis=True` → `False` (на коротких
   фразах `segment_labels` падает с IndexError).

## Вход

UTAU-подобный `.tmp` (формат utaupy.utauplugin):

```
[#VERSION]
UST Version1.2
[#SETTING]
Tempo=120
VoiceDir=<модель>
CacheDir=<кэш>
[#0000]
Length=480
Lyric=Солнце
NoteNum=60
[#0001]
Length=480
Lyric=светило
NoteNum=62
[#TRACKEND]
```

Лирика в ноте — слово кириллицей; G2P делает `enunu2nnsvs` через
`Russian_MDN.table` (→ `kana2phonemes.table`). Нот нужно ≥2.

## Запуск

`enunu_steps.main(path_tmp, path_wav, play_wav=False)` с `sys.path`:
shim → `nnsvs-master` → корень релиза. Выход — WAV.
