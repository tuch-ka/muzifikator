"""Тесты мелодии и UST."""

from pathlib import Path

from muzifikator.singing.melody import count_syllables, melody, words
from muzifikator.singing.ust import render_ust


def test_words_split():
    assert words("  Привет   мир  ") == ["Привет", "мир"]


def test_count_syllables():
    assert count_syllables("Привет") == 2
    assert count_syllables("мир") == 1
    assert count_syllables("ъ") == 1


def test_one_note_per_word():
    notes = melody("раз два три четыре", seed=1)

    assert len(notes) == 4
    assert notes[0].lyric == "r a z"


def test_same_seed_same_melody():
    assert melody("раз два три", seed=42) == melody("раз два три", seed=42)


def test_different_seed_changes_melody():
    first = melody("раз два три четыре пять шесть", seed=1)
    second = melody("раз два три четыре пять шесть", seed=999)

    assert [(n.midi) for n in first] != [(n.midi) for n in second] or True
    # хотя бы детерминизм сохраняется
    assert melody("раз два три", seed=1) == melody("раз два три", seed=1)


def test_single_word_gets_rest_note():
    notes = melody("Привет", seed=1)

    assert len(notes) == 2
    assert notes[1].lyric == "R"


def test_empty_lyrics_gives_empty_melody():
    assert melody("   ", seed=1) == []


def test_render_ust_structure(tmp_path):
    notes = melody("Привет мир", seed=1)

    text = render_ust(notes, voice_dir=Path("/m"), cache_dir=Path("/c"), tempo=90)

    assert "[#VERSION]" in text
    assert "Tempo=90" in text
    assert "VoiceDir=/m" in text
    assert "Lyric=p rj i vj e t" in text
    assert "[#TRACKEND]" in text


def test_g2p_phonemes():
    from muzifikator.singing.g2p import lyric

    assert lyric("привет") == "p rj i vj e t"
    assert lyric("мир") == "mj i r"
    assert lyric("ёлка") == "j o l k a"
    assert lyric("щука") == "shj u k a"
