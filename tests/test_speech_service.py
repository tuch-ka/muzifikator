"""Тесты сервиса речи: кэш, порции, склейка, рык, отказы."""

import shutil
import subprocess
from pathlib import Path

import pytest

from muzifikator.speech import (
    AudioProcessingError,
    EmptyTextError,
    SpeechService,
    SynthesisError,
    SynthesisRequest,
    UnknownVoiceError,
    Voice,
)
from muzifikator.speech import cache as speech_cache
from muzifikator.speech.service import split_text

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")


class FakeProvider:
    name = "fake"
    max_text_length = 40

    def __init__(self, duration: float = 0.3, fail: Exception | None = None) -> None:
        self.duration = duration
        self.fail = fail
        self.calls: list[str] = []
        self.voices = [Voice(name="voice-a", locale="ru-RU", gender="Male")]

    def list_voices(self):
        return list(self.voices)

    def synthesize(self, request, target: Path) -> None:
        self.calls.append(request.text)
        if self.fail is not None:
            raise self.fail
        if request.voice not in {voice.name for voice in self.voices}:
            raise UnknownVoiceError(f"голос не найден: {request.voice}")
        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=24000:cl=mono",
                "-t",
                str(self.duration),
                "-c:a",
                "libmp3lame",
                str(target),
            ],
            check=True,
            capture_output=True,
        )


def _service(tmp_path, provider=None, limit_mib=200) -> SpeechService:
    return SpeechService(
        provider or FakeProvider(),
        cache_dir=tmp_path / "cache",
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
        cache_limit_mib=limit_mib,
    )


def _request(**kwargs) -> SynthesisRequest:
    base = {"text": "Привет, это проверка.", "voice": "voice-a"}
    base.update(kwargs)
    return SynthesisRequest(**base)


def test_first_call_synthesizes_and_saves(tmp_path):
    provider = FakeProvider()
    service = _service(tmp_path, provider)

    result = service.synthesize(_request())

    assert result.cached is False
    assert result.provider == "fake"
    assert result.path.is_file()
    assert result.duration_seconds == pytest.approx(0.3, abs=0.15)
    assert len(provider.calls) == 1


def test_second_call_hits_cache(tmp_path):
    provider = FakeProvider()
    service = _service(tmp_path, provider)

    first = service.synthesize(_request())
    second = service.synthesize(_request())

    assert len(provider.calls) == 1
    assert second.cached is True
    assert second.path == first.path
    assert second.duration_seconds == first.duration_seconds


def test_changed_parameter_creates_new_entry(tmp_path):
    provider = FakeProvider()
    service = _service(tmp_path, provider)

    first = service.synthesize(_request())
    second = service.synthesize(_request(rate_percent=15))
    third = service.synthesize(_request(pitch_hz=-30))
    growl = service.synthesize(_request(growl=True))

    paths = {first.path, second.path, third.path, growl.path}
    assert len(paths) == 4
    assert len(provider.calls) == 4


def test_cache_survives_restart(tmp_path):
    provider = FakeProvider()
    first = _service(tmp_path, provider).synthesize(_request())

    restarted = _service(tmp_path, FakeProvider()).synthesize(_request())

    assert restarted.cached is True
    assert restarted.path == first.path


def test_growl_keeps_duration_and_is_separate(tmp_path):
    provider = FakeProvider(duration=1.0)
    service = _service(tmp_path, provider)

    plain = service.synthesize(_request())
    growly = service.synthesize(_request(growl=True))

    assert growly.growl is True
    assert growly.path != plain.path
    assert growly.duration_seconds == pytest.approx(plain.duration_seconds, abs=0.2)
    assert len(provider.calls) == 2


def test_long_text_is_chunked_and_joined(tmp_path):
    provider = FakeProvider()
    service = _service(tmp_path, provider)
    text = "Первое предложение. Второе предложение длиннее первого. Третье короткое. Четвёртое."

    result = service.synthesize(_request(text=text))

    assert len(provider.calls) > 1
    assert result.path.is_file()
    joined = " ".join(provider.calls)
    assert " ".join(joined.split()) == " ".join(text.split())
    assert not list((tmp_path / "cache").glob(".tmp-*"))


def test_short_text_is_not_chunked(tmp_path):
    provider = FakeProvider()
    service = _service(tmp_path, provider)

    service.synthesize(_request(text="Одна фраза."))

    assert len(provider.calls) == 1


def test_empty_text_is_rejected_before_provider(tmp_path):
    provider = FakeProvider()
    service = _service(tmp_path, provider)

    with pytest.raises(EmptyTextError):
        service.synthesize(_request(text="   "))

    assert provider.calls == []
    assert not list((tmp_path / "cache").glob("*.mp3"))


def test_provider_failure_leaves_no_cache_entry(tmp_path):
    provider = FakeProvider(fail=SynthesisError("сеть недоступна"))
    service = _service(tmp_path, provider)

    with pytest.raises(SynthesisError, match="сеть недоступна"):
        service.synthesize(_request())

    assert not list((tmp_path / "cache").glob("*.mp3"))


def test_unknown_voice_propagates(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(UnknownVoiceError):
        service.synthesize(_request(voice="voice-x"))


def test_broken_audio_is_reported_and_not_cached(tmp_path):
    class BrokenProvider(FakeProvider):
        def synthesize(self, request, target):
            self.calls.append(request.text)
            Path(target).write_bytes(b"not audio")

    service = _service(tmp_path, BrokenProvider())

    with pytest.raises(AudioProcessingError):
        service.synthesize(_request())

    assert not list((tmp_path / "cache").glob("*.mp3"))


def test_limit_is_applied_with_current_key(tmp_path, monkeypatch):
    captured = {}

    def fake_enforce(cache_dir, limit_bytes, *, keep_key=None):
        captured["limit_bytes"] = limit_bytes
        captured["keep_key"] = keep_key
        return []

    monkeypatch.setattr(speech_cache, "enforce_limit", fake_enforce)
    service = _service(tmp_path, limit_mib=200)

    service.synthesize(_request())

    assert captured["limit_bytes"] == 200 * 1024 * 1024
    assert captured["keep_key"] is not None


def test_split_text_keeps_content():
    text = "А. " * 30

    chunks = split_text(text, 20)

    assert all(len(chunk) <= 20 for chunk in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())


def test_split_text_rejects_bad_limit():
    with pytest.raises(ValueError):
        split_text("текст", 0)
