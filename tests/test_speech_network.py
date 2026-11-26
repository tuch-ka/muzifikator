"""Сетевой тест edge-tts: запускается только вручную через `-m network`."""

import shutil

import pytest

from muzifikator.speech import EdgeTTSProvider, SpeechService, SynthesisRequest

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
        reason="нужны ffmpeg и ffprobe",
    ),
]


def test_real_synthesis_and_cache(tmp_path):
    provider = EdgeTTSProvider()
    service = SpeechService(
        provider,
        cache_dir=tmp_path / "cache",
        ffmpeg_bin=str(shutil.which("ffmpeg")),
        ffprobe_bin=str(shutil.which("ffprobe")),
    )
    request = SynthesisRequest(text="Проверка озвучки.", voice="ru-RU-DmitryNeural")

    first = service.synthesize(request)
    second = service.synthesize(request)

    assert first.path.is_file()
    assert first.duration_seconds > 0
    assert second.cached is True
    assert second.path == first.path
