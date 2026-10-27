from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import videos
from app.core.config import get_settings
from app.main import app
from server.server import app as server_app

VIDEOS_URL = f"{get_settings().api_prefix}/videos"


def test_server_uses_shared_app() -> None:
    assert server_app is app


def test_video_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(videos, "RECORDINGS_DIR", tmp_path)
    (tmp_path / "clip.mp4").write_bytes(b"test video")
    with TestClient(server_app) as client:
        response = client.get(f"{VIDEOS_URL}/clip.mp4")
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.content == b"test video"


@pytest.mark.parametrize("filename, status_code", [("missing.mp4", 404), ("%00.mp4", 400)])
def test_missing_or_invalid_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str, status_code: int
) -> None:
    monkeypatch.setattr(videos, "RECORDINGS_DIR", tmp_path)
    with TestClient(app) as client:
        response = client.get(f"{VIDEOS_URL}/{filename}")
    assert response.status_code == status_code


def test_video_symlink_cannot_escape_recordings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside recordings")
    (recordings / "link.mp4").symlink_to(outside)
    monkeypatch.setattr(videos, "RECORDINGS_DIR", recordings)
    with TestClient(app) as client:
        response = client.get(f"{VIDEOS_URL}/link.mp4")
    assert response.status_code == 400
