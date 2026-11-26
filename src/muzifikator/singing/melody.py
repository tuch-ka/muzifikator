"""Процедурная мелодия: нота на слово, детерминизм по seed."""

from __future__ import annotations

import random
import re

from .base import Note
from .g2p import lyric as phoneme_lyric

MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
VOWELS = "аеёиоуыэюяaeiouy"
ROOT_MIDI = 60
TICKS_PER_SYLLABLE = 480
MINOR_HINTS = ("minor", "moll", "минор")


def words(lyrics: str) -> list[str]:
    return [word for word in re.split(r"\s+", lyrics.strip()) if word]


def count_syllables(word: str) -> int:
    return max(1, sum(1 for char in word.lower() if char in VOWELS))


def melody(lyrics: str, *, tags: str = "", seed: int = 0, tempo: int = 120) -> list[Note]:
    """Построить мелодию: одно слово — одна нота, длина по слогам."""
    tokens = words(lyrics)
    if not tokens:
        return []
    rng = random.Random(seed)
    scale = MINOR if any(hint in tags.lower() for hint in MINOR_HINTS) else MAJOR
    notes: list[Note] = []
    position = 0
    for index, token in enumerate(tokens):
        position = (position + rng.choice([-1, 1, 1, 2])) % len(scale)
        midi = ROOT_MIDI + scale[position]
        length = TICKS_PER_SYLLABLE * count_syllables(token)
        notes.append(Note(lyric=phoneme_lyric(token), midi=midi, length=length))
        if index % 4 == 3:
            position = 0
    last = notes[-1]
    notes[-1] = Note(lyric=last.lyric, midi=ROOT_MIDI, length=last.length)
    if len(notes) == 1:
        notes.append(Note(lyric="R", midi=ROOT_MIDI, length=TICKS_PER_SYLLABLE))
    _ = tempo  # темп читается из UST-настроек; сохраняем в сигнатуре для будущего
    return notes
