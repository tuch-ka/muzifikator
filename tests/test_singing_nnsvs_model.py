"""Реальный NNSVS-синтез: запускается только через `-m model`."""

import pytest

from muzifikator.config import Settings
from muzifikator.singing import NNSVSBackend, SingingRequest, SingingService

pytestmark = pytest.mark.model


def test_real_singing(tmp_path):
    model_dir = Settings().nnsvs_model_dir
    if not model_dir.is_dir():
        pytest.skip("модель NNSVS не скачана")

    service = SingingService(NNSVSBackend(model_dir=model_dir))
    result = service.sing(
        SingingRequest(lyrics="Привет мир как дела", tags="minor", seed=7), tmp_path
    )

    assert result.path.is_file()
    assert result.duration_seconds > 0.5


def test_real_singing_is_deterministic(tmp_path):
    model_dir = Settings().nnsvs_model_dir
    if not model_dir.is_dir():
        pytest.skip("модель NNSVS не скачана")

    service = SingingService(NNSVSBackend(model_dir=model_dir))
    request = SingingRequest(lyrics="раз два три", seed=3)
    first = service.sing(request, tmp_path / "a")
    second = service.sing(request, tmp_path / "b")

    assert first.path.read_bytes() == second.path.read_bytes()
