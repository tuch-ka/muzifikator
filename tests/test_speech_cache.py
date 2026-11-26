"""Тесты файлового кэша: ключи, sidecar, атомарность, LRU-лимит."""

import dataclasses
import json
import os

import pytest

from muzifikator.speech import SynthesisRequest, cache_key
from muzifikator.speech import cache as speech_cache
from muzifikator.speech.base import SynthesisRequest as Request


def _request(**kwargs):
    base = {"text": "привет мир", "voice": "voice-a"}
    base.update(kwargs)
    return Request(**base)


def test_same_request_same_key():
    assert cache_key("fake", _request()) == cache_key("fake", _request())


@pytest.mark.parametrize(
    "changed",
    [
        {"text": "другой текст"},
        {"voice": "voice-b"},
        {"rate_percent": 10},
        {"pitch_hz": -20},
        {"growl": True},
    ],
)
def test_any_difference_changes_key(changed):
    assert cache_key("fake", _request()) != cache_key("fake", _request(**changed))


def test_provider_changes_key():
    assert cache_key("fake", _request()) != cache_key("edge", _request())


def test_store_and_lookup(tmp_path):
    request = _request()
    key = cache_key("fake", request)
    workdir = speech_cache.temporary_directory(tmp_path)
    audio = workdir / "final.mp3"
    audio.write_bytes(b"audio-bytes")
    metadata = speech_cache.CacheMetadata.build(
        key=key, provider="fake", request=request, duration_seconds=1.5
    )

    entry = speech_cache.store(tmp_path, key=key, audio=audio, metadata=metadata)
    hit = speech_cache.lookup(tmp_path, key)

    assert hit is not None
    assert hit.audio == tmp_path / f"{key}.mp3"
    assert hit.metadata.duration_seconds == 1.5
    assert json.loads(entry.sidecar.read_text(encoding="utf-8"))["key"] == key


def test_missing_sidecar_is_a_miss(tmp_path):
    request = _request()
    key = cache_key("fake", request)
    (tmp_path / f"{key}.mp3").write_bytes(b"audio")

    assert speech_cache.lookup(tmp_path, key) is None


def test_broken_sidecar_is_a_miss(tmp_path):
    request = _request()
    key = cache_key("fake", request)
    (tmp_path / f"{key}.mp3").write_bytes(b"audio")
    (tmp_path / f"{key}.json").write_text("{не json", encoding="utf-8")

    assert speech_cache.lookup(tmp_path, key) is None


def test_foreign_sidecar_key_is_a_miss(tmp_path):
    request = _request()
    key = cache_key("fake", request)
    (tmp_path / f"{key}.mp3").write_bytes(b"audio")
    (tmp_path / f"{key}.json").write_text(json.dumps({"key": "other"}), encoding="utf-8")

    assert speech_cache.lookup(tmp_path, key) is None


def test_touch_updates_mtime(tmp_path):
    request = _request()
    key = cache_key("fake", request)
    workdir = speech_cache.temporary_directory(tmp_path)
    audio = workdir / "final.mp3"
    audio.write_bytes(b"audio")
    metadata = speech_cache.CacheMetadata.build(
        key=key, provider="fake", request=request, duration_seconds=1.0
    )
    entry = speech_cache.store(tmp_path, key=key, audio=audio, metadata=metadata)
    os.utime(entry.audio, (1_000_000, 1_000_000))
    before = entry.audio.stat().st_mtime

    speech_cache.touch(entry)

    assert entry.audio.stat().st_mtime > before


def _seed(tmp_path, key, size, mtime):
    audio = tmp_path / f"{key}.mp3"
    audio.write_bytes(b"x" * size)
    os.utime(audio, (mtime, mtime))
    sidecar = tmp_path / f"{key}.json"
    sidecar.write_text(json.dumps({"key": key}), encoding="utf-8")
    os.utime(sidecar, (mtime, mtime))


def test_limit_under_threshold_removes_nothing(tmp_path):
    _seed(tmp_path, "a", 10, 1_000)
    _seed(tmp_path, "b", 10, 2_000)

    removed = speech_cache.enforce_limit(tmp_path, limit_bytes=1_000)

    assert removed == []
    assert len(list(tmp_path.glob("*.mp3"))) == 2


def test_limit_removes_oldest_first(tmp_path):
    _seed(tmp_path, "old", 10, 1_000)
    _seed(tmp_path, "mid", 10, 2_000)
    _seed(tmp_path, "new", 10, 3_000)
    total = speech_cache.directory_size(tmp_path)

    removed = speech_cache.enforce_limit(tmp_path, limit_bytes=total - 21, keep_key="new")

    assert removed == ["old"]
    assert {path.stem for path in tmp_path.glob("*.mp3")} == {"mid", "new"}


def test_limit_never_removes_kept_key(tmp_path):
    _seed(tmp_path, "old", 10, 1_000)
    _seed(tmp_path, "fresh", 10, 900)
    total = speech_cache.directory_size(tmp_path)

    removed = speech_cache.enforce_limit(tmp_path, limit_bytes=total - 1, keep_key="fresh")

    assert removed == ["old"]
    assert (tmp_path / "fresh.mp3").exists()


def test_zero_limit_disables_eviction(tmp_path):
    _seed(tmp_path, "a", 10, 1_000)

    removed = speech_cache.enforce_limit(tmp_path, limit_bytes=0)

    assert removed == []
    assert (tmp_path / "a.mp3").exists()


def test_removal_error_does_not_raise(tmp_path, monkeypatch):
    _seed(tmp_path, "a", 10, 1_000)
    _seed(tmp_path, "b", 10, 2_000)

    def deny(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(type(tmp_path / "a.mp3"), "unlink", deny, raising=False)

    removed = speech_cache.enforce_limit(tmp_path, limit_bytes=1)

    assert removed == []


def test_request_dataclass_is_frozen():
    request = SynthesisRequest(text="a", voice="v")

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.text = "b"  # type: ignore[misc]
