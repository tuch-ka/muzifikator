"""Тесты API настроек и хранилища настроек."""

import pytest
from fastapi.testclient import TestClient

from muzifikator.api.settings_store import (
    InvalidSettingError,
    SettingsStore,
    UnknownSettingError,
)
from muzifikator.app import create_app
from muzifikator.config import Settings
from muzifikator.paths import expand
from muzifikator.preflight import BinaryStatus, PreflightResult
from muzifikator.storage import create_session_factory, init_storage


def _preflight() -> PreflightResult:
    status = BinaryStatus(name="ffmpeg", available=True, path="/bin/ffmpeg", version="9.1")
    other = BinaryStatus(name="ffprobe", available=True, path="/bin/ffprobe", version="9.1")
    return PreflightResult(ffmpeg=status, ffprobe=other)


@pytest.fixture
def factory(tmp_path):
    engine = init_storage(Settings(db_path=tmp_path / "db.sqlite3"))
    return create_session_factory(engine)


@pytest.fixture
def store(factory, tmp_path):
    return SettingsStore(
        factory,
        default_music_tags="folk metal",
        default_formats=("mp3", "m4a"),
        default_output_dir=tmp_path / "out",
    )


@pytest.fixture
def client(tmp_path, factory):
    app = create_app(
        _preflight(),
        session_factory=factory,
        settings=Settings(
            output_dir=tmp_path / "out",
            music_prompt="folk metal",
            output_formats="mp3,m4a",
        ),
    )
    with TestClient(app) as client:
        yield client


def test_defaults_when_nothing_saved(store, tmp_path):
    assert store.read() == {
        "output_dir": str(expand(tmp_path / "out")),
        "tts_voice": None,
        "music_tags": "folk metal",
        "rate_percent": 0,
        "pitch_hz": 0,
        "growl": False,
        "output_formats": ["mp3", "m4a"],
    }


def test_update_is_partial_and_persistent(store):
    updated = store.update({"tts_voice": "voice-a", "growl": True})

    assert updated["tts_voice"] == "voice-a"
    assert updated["growl"] is True
    assert updated["music_tags"] == "folk metal"
    assert store.read()["tts_voice"] == "voice-a"


def test_output_dir_is_saved_and_effective(store, tmp_path):
    target = tmp_path / "chosen"
    target.mkdir()

    updated = store.update({"output_dir": str(target)})

    assert updated["output_dir"] == str(target.resolve())
    assert store.effective_output_dir() == target.resolve()


@pytest.mark.parametrize("payload", ["out", "", "/nonexistent/path/x"])
def test_output_dir_rejects_bad_paths(store, payload):
    with pytest.raises(InvalidSettingError):
        store.update({"output_dir": payload})


def test_output_dir_rejects_file(store, tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("x", encoding="utf-8")

    with pytest.raises(InvalidSettingError):
        store.update({"output_dir": str(path)})


def test_unknown_key_is_rejected(store):
    with pytest.raises(UnknownSettingError):
        store.update({"unknown": 1})


@pytest.mark.parametrize(
    "payload",
    [
        {"rate_percent": 500},
        {"pitch_hz": -500},
        {"rate_percent": "10"},
        {"growl": "yes"},
        {"music_tags": "   "},
        {"tts_voice": ""},
        {"output_formats": []},
        {"output_formats": ["wav"]},
    ],
)
def test_invalid_values_are_rejected(store, payload):
    with pytest.raises(InvalidSettingError):
        store.update(payload)


def test_rejected_update_changes_nothing(store):
    store.update({"music_tags": "symphonic metal"})

    with pytest.raises(InvalidSettingError):
        store.update({"music_tags": "doom metal", "rate_percent": 1000})

    assert store.read()["music_tags"] == "symphonic metal"


def test_get_returns_defaults(client, tmp_path):
    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "output_dir": str(expand(tmp_path / "out")),
        "tts_voice": None,
        "music_tags": "folk metal",
        "rate_percent": 0,
        "pitch_hz": 0,
        "growl": False,
        "output_formats": ["mp3", "m4a"],
    }


def test_patch_updates_and_reads_back(client):
    response = client.patch(
        "/api/settings",
        json={"tts_voice": "voice-a", "music_tags": "symphonic metal"},
    )

    assert response.status_code == 200
    assert response.json()["tts_voice"] == "voice-a"
    assert client.get("/api/settings").json()["music_tags"] == "symphonic metal"


def test_patch_unknown_key_is_400(client):
    response = client.patch("/api/settings", json={"musicgen_model": "x"})

    assert response.status_code == 400
    assert "musicgen_model" in response.json()["detail"]


def test_patch_invalid_value_is_400(client):
    response = client.patch("/api/settings", json={"output_formats": ["wav"]})

    assert response.status_code == 400


def test_settings_survive_new_app(tmp_path, factory):
    first = create_app(
        _preflight(),
        session_factory=factory,
        settings=Settings(output_dir=tmp_path / "out"),
    )
    with TestClient(first) as client:
        client.patch("/api/settings", json={"tts_voice": "voice-a"})

    second = create_app(
        _preflight(),
        session_factory=factory,
        settings=Settings(output_dir=tmp_path / "out"),
    )
    with TestClient(second) as client:
        assert client.get("/api/settings").json()["tts_voice"] == "voice-a"


def test_settings_without_storage_is_503():
    app = create_app(_preflight())

    with TestClient(app) as client:
        assert client.get("/api/settings").status_code == 503
        assert client.patch("/api/settings", json={"growl": True}).status_code == 503
