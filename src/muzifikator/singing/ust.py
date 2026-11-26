"""Запись нот в UST-подобный временный файл для ENUNU."""

from __future__ import annotations

from pathlib import Path

from .base import Note


def render_ust(notes: list[Note], *, voice_dir: Path, cache_dir: Path, tempo: int = 120) -> str:
    """Собрать текст UST (формат utaupy.utauplugin) для enunu_steps."""
    lines = [
        "[#VERSION]",
        "UST Version1.2",
        "[#SETTING]",
        f"Tempo={tempo}",
        f"VoiceDir={voice_dir}",
        f"CacheDir={cache_dir}",
    ]
    for index, note in enumerate(notes):
        lines.extend(
            [
                f"[#{index:04d}]",
                f"Length={note.length}",
                f"Lyric={note.lyric}",
                f"NoteNum={note.midi}",
            ]
        )
    lines.append("[#TRACKEND]")
    return "\n".join(lines) + "\n"


def write_ust(
    path: Path, notes: list[Note], *, voice_dir: Path, cache_dir: Path, tempo: int = 120
) -> None:
    path.write_text(
        render_ust(notes, voice_dir=voice_dir, cache_dir=cache_dir, tempo=tempo),
        encoding="utf-8",
    )
