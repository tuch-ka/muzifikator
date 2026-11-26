"""Тесты сервиса пения на фейковом бэкенде."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from muzifikator.singing import (
    Note,
    SingingBackendError,
    SingingRequest,
    SingingRequestError,
    SingingService,
)


class FakeBackend:
    name = "fake"

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[list[Note]] = []

    def sing(self, *, notes: list[Note], tempo: int, target: Path) -> None:
        self.calls.append(list(notes))
        if self.fail is not None:
            raise self.fail
        sf.write(str(target), np.zeros(22050, dtype=np.float32), 44100)


def test_sing_returns_duration_and_seed(tmp_path):
    backend = FakeBackend()

    result = SingingService(backend).sing(SingingRequest(lyrics="Привет мир", seed=5), tmp_path)

    assert result.path.is_file()
    assert result.duration_seconds == pytest.approx(0.5, abs=0.05)
    assert result.seed == 5
    assert backend.calls


def test_random_seed_is_returned(tmp_path):
    backend = FakeBackend()

    result = SingingService(backend).sing(SingingRequest(lyrics="раз два"), tmp_path)

    assert isinstance(result.seed, int)


def test_empty_lyrics_rejected(tmp_path):
    backend = FakeBackend()

    with pytest.raises(SingingRequestError):
        SingingService(backend).sing(SingingRequest(lyrics="   "), tmp_path)

    assert backend.calls == []


def test_backend_failure_propagates(tmp_path):
    backend = FakeBackend(fail=SingingBackendError("модель упала"))

    with pytest.raises(SingingBackendError, match="модель упала"):
        SingingService(backend).sing(SingingRequest(lyrics="раз два"), tmp_path)


def test_single_word_pads_rest(tmp_path):
    backend = FakeBackend()

    SingingService(backend).sing(SingingRequest(lyrics="Привет", seed=1), tmp_path)

    notes = backend.calls[-1]
    assert len(notes) >= 2
