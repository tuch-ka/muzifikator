"""Тесты провайдера edge-tts на подменённой библиотеке (без сети)."""

import asyncio
from pathlib import Path

import pytest

from muzifikator.speech import edge as edge_module
from muzifikator.speech.base import (
    SpeechError,
    SynthesisError,
    SynthesisRequest,
    UnknownVoiceError,
    VoiceListError,
)


class FakeCommunicate:
    instances: list["FakeCommunicate"] = []
    fail_with: Exception | None = None

    def __init__(self, text, voice, *, rate, pitch):
        self.text = text
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        FakeCommunicate.instances.append(self)

    async def save(self, path: str) -> None:
        if FakeCommunicate.fail_with is not None:
            raise FakeCommunicate.fail_with
        Path(path).write_bytes(b"fake-audio")


class FakeEdgeTTS:
    voices: list[dict] = []
    list_error: Exception | None = None
    list_calls = 0
    Communicate = FakeCommunicate

    @classmethod
    async def list_voices(cls):
        cls.list_calls += 1
        if cls.list_error is not None:
            raise cls.list_error
        return cls.voices


DEFAULT_VOICES = [
    {"ShortName": "voice-a", "Locale": "ru-RU", "Gender": "Male"},
    {"ShortName": "voice-b", "Locale": "en-US", "Gender": "Female"},
]


@pytest.fixture
def fake_edge(monkeypatch):
    FakeCommunicate.instances = []
    FakeCommunicate.fail_with = None
    FakeEdgeTTS.list_error = None
    FakeEdgeTTS.list_calls = 0
    FakeEdgeTTS.voices = [dict(item) for item in DEFAULT_VOICES]
    monkeypatch.setattr(edge_module, "edge_tts", FakeEdgeTTS)
    return FakeEdgeTTS


def test_list_voices_maps_fields(fake_edge):
    provider = edge_module.EdgeTTSProvider()

    voices = provider.list_voices()

    assert [voice.name for voice in voices] == ["voice-a", "voice-b"]
    assert voices[0].locale == "ru-RU"
    assert voices[1].gender == "Female"


def test_list_voices_cached_per_process(fake_edge):
    provider = edge_module.EdgeTTSProvider()

    provider.list_voices()
    provider.list_voices()

    assert fake_edge.list_calls == 1


def test_list_voices_empty_is_error(fake_edge):
    fake_edge.voices = []
    provider = edge_module.EdgeTTSProvider()

    with pytest.raises(VoiceListError, match="пустой"):
        provider.list_voices()


def test_list_voices_failure_is_wrapped(fake_edge):
    fake_edge.list_error = RuntimeError("сеть недоступна")
    provider = edge_module.EdgeTTSProvider()

    with pytest.raises(VoiceListError, match="сеть недоступна"):
        provider.list_voices()


def test_synthesize_writes_file_and_formats_params(fake_edge, tmp_path):
    provider = edge_module.EdgeTTSProvider()
    target = tmp_path / "part.mp3"

    provider.synthesize(
        SynthesisRequest(text="привет", voice="voice-a", rate_percent=10, pitch_hz=-20),
        target,
    )

    assert target.read_bytes() == b"fake-audio"
    instance = FakeCommunicate.instances[-1]
    assert instance.rate == "+10%"
    assert instance.pitch == "-20Hz"


def test_unknown_voice_is_rejected(fake_edge, tmp_path):
    provider = edge_module.EdgeTTSProvider()

    with pytest.raises(UnknownVoiceError, match="voice-x"):
        provider.synthesize(SynthesisRequest(text="привет", voice="voice-x"), tmp_path / "a.mp3")

    assert FakeCommunicate.instances == []


def test_synthesis_failure_is_wrapped(fake_edge, tmp_path):
    FakeCommunicate.fail_with = RuntimeError("connection reset")
    provider = edge_module.EdgeTTSProvider()

    with pytest.raises(SynthesisError, match="connection reset"):
        provider.synthesize(SynthesisRequest(text="привет", voice="voice-a"), tmp_path / "a.mp3")


def test_run_sync_inside_running_loop_is_rejected():
    async def scenario():
        async def nothing():
            return None

        try:
            edge_module._run_sync(nothing(), 1.0)
        except SpeechError as exc:
            return str(exc)
        return None

    message = asyncio.run(scenario())

    assert message is not None
    assert "event loop" in message
