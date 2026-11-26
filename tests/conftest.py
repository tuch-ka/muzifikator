"""Общие фикстуры: временная база, поднятая настоящими миграциями."""

import shutil
import subprocess
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from muzifikator.config import Settings
from muzifikator.speech import Voice
from muzifikator.storage import create_session_factory, init_storage

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "test.sqlite3"


@pytest.fixture
def engine(db_path) -> Iterator[Engine]:
    engine = init_storage(Settings(db_path=db_path))
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    factory = create_session_factory(engine)
    with factory() as session:
        yield session
        session.rollback()


class FakeSpeechProvider:
    """Провайдер речи для тестов: пишет тон заданной длины в целевой файл."""

    name = "fake-speech"
    max_text_length = 1000

    def __init__(self) -> None:
        self.duration = 1.0
        self.calls: list = []
        self.fail: Exception | None = None
        self.voices_error: Exception | None = None
        self.gate = None
        self.voices = [Voice(name="voice-a", locale="ru-RU", gender="Male")]

    def list_voices(self) -> list[Voice]:
        if self.voices_error is not None:
            raise self.voices_error
        return list(self.voices)

    def synthesize(self, request, target) -> None:
        self.calls.append(request)
        if self.gate is not None:
            self.gate.wait(timeout=10)
        if self.fail is not None:
            raise self.fail
        write_tone(target, self.duration)


class FakeMusicProvider:
    """Провайдер музыки для тестов: пишет WAV нужной длины."""

    name = "fake-music"

    def __init__(self) -> None:
        self.calls: list = []
        self.fail: Exception | None = None
        self.sample_rate = 32000

    def segment(self, *, prompt: str, seconds: float, seed: int, target) -> None:
        self.calls.append((prompt, seconds, seed))
        if self.fail is not None:
            raise self.fail
        write_tone(target, seconds + 0.1, frequency=220, sample_rate=self.sample_rate)


def write_tone(path, seconds: float, *, frequency: int = 440, sample_rate: int = 24000) -> None:
    if str(path).endswith(".mp3"):
        codec = ["-c:a", "libmp3lame", "-q:a", "4"]
    else:
        codec = ["-c:a", "pcm_s16le"]
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate={sample_rate}:duration={seconds}",
            "-ac",
            "1",
            *codec,
            str(path),
        ],
        check=True,
        capture_output=True,
    )
