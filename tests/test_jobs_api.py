"""Тесты API задач: постановка, 409, стадии, файлы, голоса, восстановление."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import FFMPEG, FFPROBE, FakeMusicProvider, FakeSpeechProvider
from fastapi.testclient import TestClient

from muzifikator.api import SettingsStore
from muzifikator.app import create_app
from muzifikator.assembly import AssemblyService
from muzifikator.config import Settings
from muzifikator.jobs import JobDeps, JobManager
from muzifikator.music import MusicService
from muzifikator.preflight import BinaryStatus, PreflightResult
from muzifikator.speech import (
    SpeechService,
    SynthesisError,
    VoiceListError,
)
from muzifikator.storage import (
    create_generation,
    create_session_factory,
    get_generation,
    init_storage,
    list_generation_files,
    start_generation,
)

pytestmark = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="нужны ffmpeg и ffprobe")


def _preflight() -> PreflightResult:
    status = BinaryStatus(name="ffmpeg", available=True, path=FFMPEG, version="9.1")
    other = BinaryStatus(name="ffprobe", available=True, path=FFPROBE, version="9.1")
    return PreflightResult(ffmpeg=status, ffprobe=other)


def _build_env(tmp_path, *, speech_provider=None, min_duration=1.0):
    engine = init_storage(Settings(db_path=tmp_path / "db.sqlite3"))
    factory = create_session_factory(engine)
    speech_provider = speech_provider or FakeSpeechProvider()
    music_provider = FakeMusicProvider()
    speech = SpeechService(
        speech_provider,
        cache_dir=tmp_path / "tts",
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
    )
    music = MusicService(
        music_provider,
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
        default_prompt="folk metal",
        model_name="fake-model",
    )
    assembly = AssemblyService(
        ffmpeg_bin=str(FFMPEG),
        ffprobe_bin=str(FFPROBE),
        output_dir=tmp_path / "out",
        min_duration_seconds=min_duration,
    )
    store = SettingsStore(
        factory,
        default_music_tags="folk metal",
        default_formats=("mp3", "m4a"),
        default_output_dir=tmp_path / "out",
    )
    deps = JobDeps(
        session_factory=factory,
        speech=speech,
        music=music,
        assembly=assembly,
        resolve_output_dir=store.effective_output_dir,
        tail_seconds=assembly.tail_seconds,
        formats=("mp3", "m4a"),
    )
    manager = JobManager(deps)
    app = create_app(
        _preflight(),
        engine=engine,
        session_factory=factory,
        jobs=manager,
        settings=Settings(output_dir=tmp_path / "out"),
        store=store,
    )
    return SimpleNamespace(
        app=app,
        factory=factory,
        manager=manager,
        speech_provider=speech_provider,
        music_provider=music_provider,
        tmp_path=tmp_path,
    )


@pytest.fixture
def env(tmp_path):
    environment = _build_env(tmp_path)
    with TestClient(environment.app) as client:
        environment.client = client
        yield environment


def _wait(client, generation_id: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/generations/{generation_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"done", "failed"}:
            return body
        time.sleep(0.05)
    raise AssertionError("задача не завершилась за отведённое время")


def _post(client, **overrides):
    payload = {"text": "Привет, мир!", "voice": "voice-a"}
    payload.update(overrides)
    return client.post("/api/generations", json=payload)


def test_generation_finishes_and_stores_files(env):
    response = _post(env.client)

    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "pending"

    body = _wait(env.client, created["id"])
    assert body["status"] == "done"
    assert body["duration_seconds"] == pytest.approx(3.0, abs=0.3)
    assert set(body["files"]) == {"mp3", "m4a"}
    for path in body["files"].values():
        assert path.endswith((".mp3", ".m4a"))

    with env.factory() as session:
        rows = list_generation_files(session, created["id"])
    assert {row.format for row in rows} == {"mp3", "m4a"}


def test_busy_generation_returns_conflict(tmp_path):
    provider = FakeSpeechProvider()
    provider.gate = threading.Event()
    environment = _build_env(tmp_path, speech_provider=provider)

    with TestClient(environment.app) as client:
        first = _post(client).json()
        deadline = time.monotonic() + 10
        while not provider.calls and time.monotonic() < deadline:
            time.sleep(0.02)

        second = _post(client)

        assert second.status_code == 409
        detail = second.json()["detail"]
        assert detail["generation_id"] == first["id"]

        provider.gate.set()
        assert _wait(client, first["id"])["status"] == "done"


def test_failed_stage_marks_task_failed(env):
    env.speech_provider.fail = SynthesisError("сеть недоступна")

    created = _post(env.client).json()
    body = _wait(env.client, created["id"])

    assert body["status"] == "failed"
    assert "сеть недоступна" in body["error"]
    assert body["files"] == {}


def test_unknown_voice_is_rejected(env):
    response = _post(env.client, voice="voice-x")

    assert response.status_code == 400
    assert "voice-x" in response.json()["detail"]


def test_unknown_format_is_rejected(env):
    response = _post(env.client, formats=["wav"])

    assert response.status_code == 400


def test_empty_text_is_rejected(env):
    response = _post(env.client, text="   ")

    assert response.status_code == 422


def test_unknown_generation_is_404(env):
    response = env.client.get("/api/generations/нет-такой")

    assert response.status_code == 404


def test_voices_endpoint(env):
    response = env.client.get("/api/voices")

    assert response.status_code == 200
    assert response.json() == [{"name": "voice-a", "locale": "ru-RU", "gender": "Male"}]


def test_voices_provider_failure_is_502(env):
    env.speech_provider.voices_error = VoiceListError("нет сети")

    response = env.client.get("/api/voices")

    assert response.status_code == 502


def test_history_lists_newest_first(env):
    first = _post(env.client).json()
    _wait(env.client, first["id"])

    response = env.client.get("/api/generations?limit=5")

    assert response.status_code == 200
    items = response.json()
    assert items and items[0]["id"] == first["id"]


def test_stale_running_is_failed_on_startup(tmp_path):
    environment = _build_env(tmp_path)
    with environment.factory() as session:
        generation = create_generation(session, text="прерванная")
        start_generation(session, generation.id)
        session.commit()
        generation_id = generation.id

    with TestClient(environment.app) as client:
        response = client.get(f"/api/generations/{generation_id}")

    body = response.json()
    assert body["status"] == "failed"
    assert "перезапуск" in body["error"]


def test_endpoints_require_jobs():
    app = create_app(_preflight())

    with TestClient(app) as client:
        response = client.post("/api/generations", json={"text": "Привет", "voice": "voice-a"})
        health = client.get("/api/health")

    assert response.status_code == 503
    assert health.status_code == 200


def test_settings_become_generation_defaults(env):
    patched = env.client.patch(
        "/api/settings",
        json={"tts_voice": "voice-a", "music_tags": "symphonic metal", "output_formats": ["mp3"]},
    )
    assert patched.status_code == 200

    created = env.client.post("/api/generations", json={"text": "Только текст"}).json()
    body = _wait(env.client, created["id"])

    assert body["status"] == "done"
    assert set(body["files"]) == {"mp3"}
    assert env.music_provider.calls[-1][0] == "symphonic metal"
    with env.factory() as session:
        stored = get_generation(session, created["id"])
        assert stored.voice == "voice-a"
        assert stored.music_tags == "symphonic metal"


def test_missing_voice_without_settings_is_rejected(env):
    response = env.client.post("/api/generations", json={"text": "Без голоса"})

    assert response.status_code == 422


def test_explicit_parameters_override_settings(env):
    env.client.patch(
        "/api/settings",
        json={"tts_voice": "voice-a", "music_tags": "folk metal"},
    )

    created = _post(env.client, music_tags="symphonic metal").json()
    _wait(env.client, created["id"])

    assert env.music_provider.calls[-1][0] == "symphonic metal"
    settings = env.client.get("/api/settings").json()
    assert settings["music_tags"] == "folk metal"


def test_output_dir_setting_changes_target(env):
    target = env.tmp_path / "chosen"
    target.mkdir()
    patched = env.client.patch("/api/settings", json={"output_dir": str(target)})
    assert patched.status_code == 200

    created = _post(env.client).json()
    body = _wait(env.client, created["id"])

    assert body["status"] == "done"
    for path in body["files"].values():
        assert Path(path).is_absolute()
        assert Path(path).parent == target.resolve()
        assert Path(path).is_file()

    listing = env.client.get("/api/files").json()
    assert {entry["name"] for entry in listing["files"]} == {
        Path(path).name for path in body["files"].values()
    }
