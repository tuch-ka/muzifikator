"""Тесты библиотеки файлов: список, медиа, открытие, удаление, каталог."""

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from muzifikator.api import SettingsStore
from muzifikator.api.library import reveal_command
from muzifikator.app import create_app
from muzifikator.config import Settings
from muzifikator.preflight import BinaryStatus, PreflightResult
from muzifikator.storage import (
    add_generation_file,
    create_generation,
    create_session_factory,
    finish_generation,
    init_storage,
    start_generation,
)


def _preflight() -> PreflightResult:
    status = BinaryStatus(name="ffmpeg", available=True, path="/bin/ffmpeg", version="9.1")
    other = BinaryStatus(name="ffprobe", available=True, path="/bin/ffprobe", version="9.1")
    return PreflightResult(ffmpeg=status, ffprobe=other)


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "out").mkdir(parents=True)
    monkeypatch.setattr("muzifikator.api.library.home_root", lambda: home.resolve())
    engine = init_storage(Settings(db_path=tmp_path / "db.sqlite3"))
    factory = create_session_factory(engine)
    store = SettingsStore(
        factory,
        default_music_tags="folk metal",
        default_formats=("mp3", "m4a"),
        default_output_dir=home / "out",
    )
    app = create_app(
        _preflight(),
        session_factory=factory,
        store=store,
        settings=Settings(output_dir=home / "out"),
    )
    with TestClient(app) as client:
        yield {
            "client": client,
            "factory": factory,
            "store": store,
            "home": home,
            "out": home / "out",
        }


def _add_generation(
    factory,
    *,
    out_dir: Path,
    name: str,
    formats: tuple[str, ...] = ("mp3", "m4a"),
    created_at: datetime | None = None,
    create_files: bool = True,
):
    paths: dict[str, Path] = {}
    with factory() as session:
        generation = create_generation(session, text="Текст", voice="voice-a", generation_id=None)
        if created_at is not None:
            generation.created_at = created_at
        start_generation(session, generation.id)
        for fmt in formats:
            path = out_dir / f"{name}.{fmt}"
            if create_files:
                path.write_bytes(b"audio-bytes-" + fmt.encode())
            add_generation_file(session, generation.id, format=fmt, path=str(path))
            paths[fmt] = path
        finish_generation(
            session,
            generation.id,
            output_path=str(paths[formats[0]]),
            duration_seconds=20.0,
        )
        session.commit()
        return generation.id, paths


def test_list_returns_db_entries(env):
    _add_generation(env["factory"], out_dir=env["out"], name="первый")

    response = env["client"].get("/api/files")

    assert response.status_code == 200
    body = response.json()
    assert len(body["files"]) == 2
    assert body["has_more"] is False
    formats = {entry["format"] for entry in body["files"]}
    assert formats == {"mp3", "m4a"}
    assert all(entry["exists"] for entry in body["files"])
    assert all(Path(entry["path"]).is_absolute() for entry in body["files"])


def test_list_newest_first_and_limited(env):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    _add_generation(
        env["factory"], out_dir=env["out"], name="старый", formats=("mp3",), created_at=base
    )
    newer, _ = _add_generation(
        env["factory"],
        out_dir=env["out"],
        name="новый",
        formats=("mp3",),
        created_at=base + timedelta(hours=1),
    )

    body = env["client"].get("/api/files?limit=1").json()

    assert len(body["files"]) == 1
    assert body["files"][0]["generation_id"] == newer
    assert body["has_more"] is True


def test_list_marks_missing_files(env):
    _, paths = _add_generation(
        env["factory"], out_dir=env["out"], name="исчезнет", formats=("mp3",)
    )
    paths["mp3"].unlink()

    body = env["client"].get("/api/files").json()

    assert body["files"][0]["exists"] is False
    assert body["files"][0]["size"] is None


def test_list_ignores_unknown_files(env):
    (env["out"] / "чужой.mp3").write_bytes(b"x")
    _add_generation(env["factory"], out_dir=env["out"], name="свой", formats=("mp3",))

    body = env["client"].get("/api/files").json()

    assert [Path(entry["path"]).name for entry in body["files"]] == ["свой.mp3"]


def test_media_served_with_range(env):
    generation_id, _ = _add_generation(
        env["factory"], out_dir=env["out"], name="плеер", formats=("mp3",)
    )

    full = env["client"].get(f"/api/generations/{generation_id}/files/mp3/media")
    partial = env["client"].get(
        f"/api/generations/{generation_id}/files/mp3/media",
        headers={"Range": "bytes=0-4"},
    )

    assert full.status_code == 200
    assert full.headers["content-type"] == "audio/mpeg"
    assert full.headers["accept-ranges"] == "bytes"
    assert partial.status_code == 206
    assert partial.headers["content-range"].startswith("bytes 0-4/")


def test_media_missing_file_is_404(env):
    generation_id, paths = _add_generation(
        env["factory"], out_dir=env["out"], name="нет", formats=("mp3",)
    )
    paths["mp3"].unlink()

    response = env["client"].get(f"/api/generations/{generation_id}/files/mp3/media")

    assert response.status_code == 404


def test_media_unknown_record_is_404(env):
    response = env["client"].get("/api/generations/нет/files/mp3/media")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("darwin", ["open", "-R"]),
        ("win32", ["explorer", "/select,"]),
        ("linux", ["xdg-open"]),
    ],
)
def test_reveal_command_per_platform(tmp_path, platform, expected):
    target = tmp_path / "x.mp3"

    command = reveal_command(target, platform)

    assert command[0] == expected[0]
    if platform == "win32":
        assert command[1].startswith("/select,")
    elif platform == "darwin":
        assert command[1] == "-R"
        assert command[2] == str(target)


def test_reveal_runs_command(env, monkeypatch):
    generation_id, _ = _add_generation(
        env["factory"], out_dir=env["out"], name="открыть", formats=("mp3",)
    )
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("muzifikator.api.library.subprocess.run", fake_run)

    response = env["client"].post(f"/api/generations/{generation_id}/files/mp3/reveal")

    assert response.status_code == 204
    assert calls and calls[0][0] in {"open", "explorer", "xdg-open"}


def test_reveal_command_failure_is_502(env, monkeypatch):
    generation_id, _ = _add_generation(
        env["factory"], out_dir=env["out"], name="сбой", formats=("mp3",)
    )

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "cannot open")

    monkeypatch.setattr("muzifikator.api.library.subprocess.run", fake_run)

    response = env["client"].post(f"/api/generations/{generation_id}/files/mp3/reveal")

    assert response.status_code == 502
    assert "cannot open" in response.json()["detail"]


def test_delete_removes_files_and_rows(env):
    generation_id, paths = _add_generation(env["factory"], out_dir=env["out"], name="удалить")

    response = env["client"].delete(f"/api/generations/{generation_id}")

    assert response.status_code == 204
    assert not any(path.exists() for path in paths.values())
    assert env["client"].get("/api/files").json()["files"] == []
    assert env["client"].get(f"/api/generations/{generation_id}").status_code == 404


def test_delete_tolerates_missing_file(env):
    generation_id, paths = _add_generation(env["factory"], out_dir=env["out"], name="частично")
    paths["mp3"].unlink()

    response = env["client"].delete(f"/api/generations/{generation_id}")

    assert response.status_code == 204
    assert not paths["m4a"].exists()


def test_delete_unknown_is_404(env):
    assert env["client"].delete("/api/generations/нет").status_code == 404


def test_delete_failure_keeps_rows(env, monkeypatch):
    generation_id, paths = _add_generation(
        env["factory"], out_dir=env["out"], name="занят", formats=("mp3",)
    )
    blocked = paths["mp3"]
    original_unlink = Path.unlink

    def fake_unlink(self, missing_ok=False):
        if self == blocked:
            raise PermissionError("denied")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    response = env["client"].delete(f"/api/generations/{generation_id}")

    assert response.status_code == 502
    monkeypatch.setattr(Path, "unlink", original_unlink)
    assert env["client"].get("/api/files").json()["files"] != []


def test_storage_info(env):
    body = env["client"].get("/api/storage").json()

    assert body["path"] == str((env["home"] / "out").resolve())


def test_browse_home_and_subdir(env):
    (env["home"] / "music").mkdir()
    (env["home"] / "out" / "nested").mkdir()

    root = env["client"].get("/api/storage/browse").json()
    nested = (
        env["client"].get("/api/storage/browse", params={"path": str(env["home"] / "out")}).json()
    )

    assert root["path"] == str(env["home"].resolve())
    assert root["parent"] is None
    assert {entry["name"] for entry in root["entries"]} == {"music", "out"}
    assert nested["parent"] == str(env["home"].resolve())
    assert [entry["name"] for entry in nested["entries"]] == ["nested"]


def test_browse_outside_home_is_400(env, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    response = env["client"].get("/api/storage/browse", params={"path": str(outside)})

    assert response.status_code == 400


def test_browse_missing_is_400(env):
    response = env["client"].get("/api/storage/browse", params={"path": str(env["home"] / "nope")})

    assert response.status_code == 400


def test_browse_shows_only_directories(env):
    (env["home"] / "file.txt").write_text("x", encoding="utf-8")
    (env["home"] / "dir").mkdir()

    body = env["client"].get("/api/storage/browse").json()

    names = [entry["name"] for entry in body["entries"]]
    assert "dir" in names
    assert "file.txt" not in names
