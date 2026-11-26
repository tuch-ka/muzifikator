"""Разборчивость через faster-whisper: WER относительно опорного текста."""

from __future__ import annotations

import sys
from pathlib import Path

from faster_whisper import WhisperModel


import re


def normalize(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-zа-яё0-9 ]", " ", text.lower())
    return [w for w in cleaned.split() if w]


def wer(reference: str, hypothesis: str) -> float:
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    if not ref:
        return 0.0
    # простейшее расстояние Левенштейна по словам
    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]),
            )
    return d[len(ref)][len(hyp)] / len(ref)


def transcribe(audio: str, reference: str, model_size: str = "small") -> float:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio, language="ru")
    hypothesis = " ".join(segment.text for segment in segments)
    return wer(reference, hypothesis), hypothesis


if __name__ == "__main__":
    score, hyp = transcribe(sys.argv[1], sys.argv[2])
    print(f"WER={score:.3f}")
    print("ASR:", hyp)
