"""Тесты API файлов: листинг и защита путей."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from muzifikator.app import create_app
from muzifikator.config import Settings
from muzifikator.preflight import BinaryStatus, PreflightResult


def _preflight() -> PreflightResult:
    status = BinaryStatus(name="ffmpeg", available=True, path="/bin/ffmpeg", version="9.1")
    other = BinaryStatus(name="ffprobe", available=True, path="/bin/ffprobe", version="9.1")
    return PreflightResult(ffmpeg=status, ffprobe=other)


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "out"
    root.mkdir()
    (root / "b.mp3").write_bytes(b"12345")
    (root / "a.m4a").write_bytes(b"12")
    (root / ".tmp-partial.mp3").write_bytes(b"")
    nested = root / "sub"
    nested.mkdir()
    (nested / "inner.mp3").write_bytes(b"1")
    return root


@pytest.fixture
def client(root):
    app = create_app(_preflight(), settings=Settings(output_dir=root))
    with TestClient(app) as client:
        yield client


def test_root_listing(client, root):
    response = client.get("/api/files")

    assert response.status_code == 200
    body = response.json()
    assert body["root"] == str(root.resolve())
    assert body["path"] == ""
    names = [(entry["kind"], entry["name"]) for entry in body["entries"]]
    assert names == [
        ("dir", "sub"),
        ("file", ".tmp-partial.mp3"),
        ("file", "a.m4a"),
        ("file", "b.mp3"),
    ]
    by_name = {entry["name"]: entry for entry in body["entries"]}
    assert by_name["b.mp3"]["size"] == 5
    assert by_name["sub"]["size"] is None
    assert by_name["b.mp3"]["path"] == "b.mp3"


def test_nested_listing(client):
    response = client.get("/api/files", params={"path": "sub"})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "sub"
    assert [entry["path"] for entry in body["entries"]] == ["sub/inner.mp3"]


def test_empty_directory(client, root):
    (root / "empty").mkdir()

    response = client.get("/api/files", params={"path": "empty"})

    assert response.status_code == 200
    assert response.json()["entries"] == []


@pytest.mark.parametrize("path", ["../", "..", "sub/../../"])
def test_traversal_is_rejected(client, path):
    response = client.get("/api/files", params={"path": path})

    assert response.status_code == 400


def test_absolute_path_is_rejected(client):
    response = client.get("/api/files", params={"path": "/etc"})

    assert response.status_code == 400


def test_symlink_outside_is_rejected(client, root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, root / "link")

    response = client.get("/api/files", params={"path": "link"})

    assert response.status_code == 400


def test_missing_directory_is_404(client):
    response = client.get("/api/files", params={"path": "nope"})

    assert response.status_code == 404


def test_file_path_is_rejected(client):
    response = client.get("/api/files", params={"path": "b.mp3"})

    assert response.status_code == 400


def test_root_is_created(tmp_path):
    target = tmp_path / "fresh" / "out"
    app = create_app(_preflight(), settings=Settings(output_dir=target))

    with TestClient(app) as client:
        response = client.get("/api/files")

    assert response.status_code == 200
    assert target.is_dir()
    assert json.loads(response.text)["entries"] == []
