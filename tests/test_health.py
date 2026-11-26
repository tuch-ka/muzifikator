"""Тесты health-эндпоинта."""

import subprocess

import pytest
from fastapi.testclient import TestClient

from muzifikator import preflight
from muzifikator.app import create_app
from muzifikator.preflight import BinaryStatus, PreflightResult


@pytest.fixture
def snapshot():
    return PreflightResult(
        ffmpeg=BinaryStatus(name="ffmpeg", available=True, path="/usr/bin/ffmpeg", version="7.1"),
        ffprobe=BinaryStatus(
            name="ffprobe", available=True, path="/usr/bin/ffprobe", version="7.1"
        ),
    )


@pytest.fixture
def client(snapshot):
    return TestClient(create_app(snapshot))


def test_health_reports_versions_and_paths(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_version"]
    assert body["binaries"]["ffmpeg"] == {
        "available": True,
        "path": "/usr/bin/ffmpeg",
        "version": "7.1",
    }
    assert body["binaries"]["ffprobe"]["available"] is True


def test_health_keeps_fields_when_version_unknown():
    snapshot = PreflightResult(
        ffmpeg=BinaryStatus(name="ffmpeg", available=True, path="/x/ffmpeg", version=None),
        ffprobe=BinaryStatus(name="ffprobe", available=True, path="/x/ffprobe", version=None),
    )
    body = TestClient(create_app(snapshot)).get("/api/health").json()

    assert body["binaries"]["ffmpeg"]["version"] is None
    assert body["binaries"]["ffmpeg"]["path"] == "/x/ffmpeg"


def test_health_does_not_spawn_processes(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("health не должен запускать внешние процессы")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(preflight.shutil, "which", forbidden)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_health_rejects_post(client):
    assert client.post("/api/health").status_code == 405


def test_health_does_not_leak_environment(client, monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "super-secret-value")

    body = client.get("/api/health").text

    assert "SECRET_TOKEN" not in body
    assert "super-secret-value" not in body
