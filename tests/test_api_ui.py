"""Тесты отдачи статического интерфейса."""

import re

from fastapi.testclient import TestClient

from muzifikator.app import create_app
from muzifikator.preflight import BinaryStatus, PreflightResult


def _preflight() -> PreflightResult:
    status = BinaryStatus(name="ffmpeg", available=True, path="/bin/ffmpeg", version="9.1")
    other = BinaryStatus(name="ffprobe", available=True, path="/bin/ffprobe", version="9.1")
    return PreflightResult(ffmpeg=status, ffprobe=other)


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(_preflight()))


def test_index_page_served(tmp_path):
    with _client(tmp_path) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    for element_id in (
        "generation-form",
        "text",
        "voice",
        "tags",
        "mode",
        "storage-path",
        "storage-browser",
        "browser-list",
        "player",
        "files-list",
    ):
        assert f'id="{element_id}"' in html
    assert 'id="folder"' not in html
    assert "/static/app.js" in html
    assert "/static/style.css" in html


def test_index_has_no_external_resources(tmp_path):
    with _client(tmp_path) as client:
        html = client.get("/").text

    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert external == []


def test_static_assets_served(tmp_path):
    with _client(tmp_path) as client:
        script = client.get("/static/app.js")
        styles = client.get("/static/style.css")

    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    for marker in ("/api/files", "/api/storage/browse", "/media", "/reveal", "DELETE", "mode"):
        assert marker in script.text
    assert styles.status_code == 200
    assert "text/css" in styles.headers["content-type"]


def test_health_still_works_with_ui_mounted(tmp_path):
    with _client(tmp_path) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
