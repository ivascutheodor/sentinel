from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from conftest import API
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select, update

from app.core.config import get_settings
from app.db.enums import VideoStatus
from app.db.models import AuditLog, VideoClip
from app.main import app

VIDEOS_URL = f"{API}/videos"
EVENTS_URL = f"{API}/events"
WORKER_HEADERS = {"X-API-Key": get_settings().worker_api_key.get_secret_value()}


@pytest.fixture
def clip(db_client: TestClient, recordings: Path, camera_name: str) -> dict[str, Any]:
    """A `ready` clip in the database with its file in the temporary recordings/ folder."""
    name = f"incident_{uuid4().hex}.mp4"
    (recordings / name).write_bytes(b"test video")
    body = {
        "camera_id": camera_name,
        "video_path": name,
        "recorded_start_at": "2026-10-08T09:59:55Z",
        "recorded_end_at": "2026-10-08T10:00:25Z",
        "size_bytes": 10,
    }
    response = db_client.post(EVENTS_URL, json=body, headers=WORKER_HEADERS)
    assert response.status_code == 201, response.text
    return response.json()["clips"][0]


def views(connection: Connection, clip: dict[str, Any]) -> int:
    return connection.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "clip.view", AuditLog.resource_id == clip["id"])
    )


def test_video_requires_login() -> None:
    with TestClient(app) as anonymous:
        assert anonymous.get(f"{VIDEOS_URL}/clip.mp4").status_code == 401


def test_ready_clip_plays_and_is_audited_once(
    db_client: TestClient, db_connection: Connection, clip: dict[str, Any]
) -> None:
    response = db_client.get(f"{VIDEOS_URL}/{clip['filepath']}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == b"test video"
    assert views(db_connection, clip) == 1

    # The browser's follow-up chunks are not separate viewings...
    response = db_client.get(f"{VIDEOS_URL}/{clip['filepath']}", headers={"Range": "bytes=5-"})
    assert response.status_code == 206
    assert response.content == b"video"
    assert views(db_connection, clip) == 1
    # ...but opening it again from the start is.
    db_client.get(f"{VIDEOS_URL}/{clip['filepath']}", headers={"Range": "bytes=0-"})
    assert views(db_connection, clip) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": datetime.now(UTC) - timedelta(minutes=1)},
        {"status": VideoStatus.DELETING, "delete_requested_at": datetime.now(UTC)},
    ],
    ids=["expired", "being deleted"],
)
def test_clip_that_is_not_viewable_is_not_found(
    db_client: TestClient,
    db_connection: Connection,
    clip: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    db_connection.execute(update(VideoClip).where(VideoClip.id == clip["id"]).values(**changes))
    assert db_client.get(f"{VIDEOS_URL}/{clip['filepath']}").status_code == 404
    assert views(db_connection, clip) == 0


def test_pending_clip_is_not_found(
    db_client: TestClient, recordings: Path, camera_name: str
) -> None:
    (recordings / "pending.mp4").write_bytes(b"still being written")
    body = {"camera_id": camera_name, "video_path": "pending.mp4"}
    assert db_client.post(EVENTS_URL, json=body, headers=WORKER_HEADERS).status_code == 201
    assert db_client.get(f"{VIDEOS_URL}/pending.mp4").status_code == 404


def test_file_unknown_to_the_database_is_not_found(db_client: TestClient, recordings: Path) -> None:
    (recordings / "unregistered.mp4").write_bytes(b"not a clip")
    assert db_client.get(f"{VIDEOS_URL}/unregistered.mp4").status_code == 404


def test_clip_whose_file_is_missing_is_not_found(
    db_client: TestClient, recordings: Path, clip: dict[str, Any]
) -> None:
    (recordings / clip["filepath"]).unlink()
    assert db_client.get(f"{VIDEOS_URL}/{clip['filepath']}").status_code == 404


@pytest.mark.parametrize("filename", ["%00.mp4", "..%5Csecret.mp4", "c:secret.mp4"])
def test_invalid_file_name(db_client: TestClient, recordings: Path, filename: str) -> None:
    assert db_client.get(f"{VIDEOS_URL}/{filename}").status_code == 400


def test_video_symlink_cannot_escape_recordings(
    db_client: TestClient, recordings: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside") / "outside.mp4"
    outside.write_bytes(b"outside recordings")
    try:
        (recordings / "link.mp4").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks needs extra privileges on Windows")
    assert db_client.get(f"{VIDEOS_URL}/link.mp4").status_code == 400
