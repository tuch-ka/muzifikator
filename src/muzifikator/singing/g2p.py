"""Русская графема → фонемы в алфавите голосового банка (Russian_MDN.table)."""

from __future__ import annotations

VOWELS = "аеёиоуыэюя"
IOTATED = "еёюя"
VOWEL_MAP = {
    "а": "a",
    "о": "o",
    "у": "u",
    "ы": "y",
    "э": "e",
    "и": "i",
    "е": "e",
    "ё": "o",
    "ю": "u",
    "я": "a",
}
CONSONANTS = {
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "ж": "zh",
    "з": "z",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "shj",
}
ALWAYS_HARD = set("жшц")
ALWAYS_SOFT = set("чщ")
PALATALIZE_BEFORE = set("еёиюяь")


def phonemes(word: str) -> list[str]:
    """Слово → список фонем. Неизвестные символы пропускаются."""
    chars = [c for c in word.lower() if c.isalpha()]
    result: list[str] = []
    for index, char in enumerate(chars):
        nxt = chars[index + 1] if index + 1 < len(chars) else ""
        prev = chars[index - 1] if index > 0 else ""
        if char in VOWELS:
            iotate = index == 0 or prev in VOWELS or prev in "ъьй"
            if char in IOTATED and iotate:
                result.append("j")
            result.append(VOWEL_MAP[char])
        elif char in CONSONANTS:
            phoneme = CONSONANTS[char]
            if nxt in PALATALIZE_BEFORE and char not in ALWAYS_HARD and char not in ALWAYS_SOFT:
                phoneme += "j"
            result.append(phoneme)
        elif char == "й":
            result.append("j")
        elif char in "ъь":
            continue
    return result


def lyric(word: str) -> str:
    """Фонемная строка для ноты UST (пробелы — разделители фонем)."""
    tokens = phonemes(word)
    return " ".join(tokens) if tokens else "a"
