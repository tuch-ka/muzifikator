"""D: русская речь edge-tts -> перенос F0 на мелодию через WORLD."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import edge_tts
import numpy as np
import pyworld as pw
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from melody import melody  # noqa: E402


async def synthesize_speech(text: str, voice: str, path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(path))


def robot_sing(text: str, *, tags: str, voice: str, out: Path, sr: int = 24000) -> None:
    speech = out.with_suffix(".speech.wav")
    asyncio.run(synthesize_speech(text, voice, speech))
    samples, rate = sf.read(str(speech))
    samples = samples.astype(np.float64)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    notes = melody(text, tags=tags)
    # целевой контур F0: натянуть ноты на всю длину речи
    frame_period = 5.0  # мс
    f0, time_axis = pw.harvest(samples, rate, frame_period=frame_period)
    spectral = pw.cheaptrick(samples, f0, time_axis, rate)
    aperiodicity = pw.d4c(samples, f0, time_axis, rate)

    n_frames = len(time_axis)
    note_f0 = np.array([440.0 * 2 ** ((n.midi - 69) / 12) for n in notes])
    # равномерно распределяем ноты по кадрам
    indices = np.clip(
        (np.linspace(0, len(notes) - 1, n_frames)).astype(int), 0, len(notes) - 1
    )
    target_f0 = note_f0[indices]

    synthesized = pw.synthesize(target_f0, spectral, aperiodicity, rate, frame_period)
    synthesized = (synthesized * 32767).clip(-32768, 32767).astype(np.int16)
    sf.write(str(out), synthesized, rate)


if __name__ == "__main__":
    robot_sing(
        sys.argv[1] if len(sys.argv) > 1 else "Солнце светило очень ярко",
        tags="minor",
        voice="ru-RU-DmitryNeural",
        out=Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/nnsvs-eval/robot.wav"),
    )
