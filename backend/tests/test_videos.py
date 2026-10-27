from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import videos
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.main import app

VIDEOS_URL = f"{get_settings().api_prefix}/videos"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client whose requests count as logged in."""
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_video_requires_login() -> None:
    with TestClient(app) as anonymous:
        assert anonymous.get(f"{VIDEOS_URL}/clip.mp4").status_code == 401


def test_video_download(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(videos, "RECORDINGS_DIR", tmp_path)
    (tmp_path / "clip.mp4").write_bytes(b"test video")
    response = client.get(f"{VIDEOS_URL}/clip.mp4")
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == b"test video"


@pytest.mark.parametrize(
    "filename, status_code",
    [("missing.mp4", 404), ("%00.mp4", 400), ("..%5Csecret.mp4", 400)],
)
def test_missing_or_invalid_video(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    status_code: int,
) -> None:
    monkeypatch.setattr(videos, "RECORDINGS_DIR", tmp_path)
    response = client.get(f"{VIDEOS_URL}/{filename}")
    assert response.status_code == status_code


def test_video_symlink_cannot_escape_recordings(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside recordings")
    try:
        (recordings / "link.mp4").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks needs extra privileges on Windows")
    monkeypatch.setattr(videos, "RECORDINGS_DIR", recordings)
    response = client.get(f"{VIDEOS_URL}/link.mp4")
    assert response.status_code == 400
