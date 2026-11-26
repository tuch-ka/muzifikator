"""Процедурная мелодия: нота на слог, тональность и темп из тегов."""

from __future__ import annotations

from dataclasses import dataclass

MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]

DEFAULT_ROOT = 57  # A3


@dataclass(frozen=True)
class Note:
    syllable: str
    midi: int
    seconds: float


def syllables(text: str) -> list[str]:
    """Грубый счёт слогов по гласным — для распределения нот."""
    vowels = "аеёиоуыэюяaeiouy"
    out: list[str] = []
    current = ""
    for char in text.lower():
        if char.isalpha():
            current += char
            if char in vowels:
                out.append(current)
                current = ""
        elif current:
            out.append(current)
            current = ""
    if current:
        out.append(current)
    return out or ["а"]


def melody(text: str, *, tags: str = "", root: int = DEFAULT_ROOT) -> list[Note]:
    scale = MINOR if "minor" in tags.lower() else MAJOR
    syls = syllables(text)
    notes: list[Note] = []
    # простое движение по гамме с шагом вниз в конце фразы
    position = 0
    for index, syl in enumerate(syls):
        if index and index % 4 == 0:
            position = (position + 2) % 7
        midi = root + scale[position]
        seconds = 0.4
        notes.append(Note(syllable=syl, midi=midi, seconds=seconds))
        if index % 3 == 2:
            position = (position + 1) % 7
    if notes:
        last = notes[-1]
        notes[-1] = Note(last.syllable, root, 0.8)
    return notes
