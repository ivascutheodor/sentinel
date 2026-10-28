from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, insert, select, update

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import Camera, Event, SystemSettings, VideoClip
from app.main import app

EVENTS_URL = f"{get_settings().api_prefix}/events"
WORKER_HEADERS = {"X-API-Key": get_settings().worker_api_key.get_secret_value()}


@pytest.fixture
def camera_name() -> str:
    return f"test-camera-{uuid4().hex}"


@pytest.fixture
def event_payload(camera_name: str) -> dict[str, Any]:
    """A complete body, as the worker sends it."""
    return {
        "camera_id": camera_name,
        "video_path": f"incident_{uuid4().hex}.mp4",
        "started_at": "2026-10-08T10:00:00Z",
        "last_person_seen_at": "2026-10-08T10:00:20Z",
        "closed_at": "2026-10-08T10:00:25Z",
        "end_reason": "person_absent",
        "recorded_start_at": "2026-10-08T09:59:55Z",
        "recorded_end_at": "2026-10-08T10:00:25Z",
        "size_bytes": 4096,
        "config_snapshot": {
            "schema_version": 1,
            "model_ref": "yolo11n.pt",
            "detection_config": {"schema_version": 1, "region": None},
            "settings": {"pre_roll_seconds": 5, "post_roll_seconds": 5},
        },
    }


@pytest.fixture
def db_client(db_app: None, db_connection: Connection, camera_name: str) -> Iterator[TestClient]:
    """A logged-in client whose requests run inside the rolled-back test transaction."""
    db_connection.execute(
        insert(Camera).values(name=camera_name, stream_url=f"rtsp://{camera_name}/stream")
    )
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_create_read_and_delete_event(
    db_client: TestClient, db_connection: Connection, event_payload: dict[str, Any]
) -> None:
    response = db_client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert response.status_code == 201, response.text
    created = response.json()
    event_id = UUID(created["id"])
    assert created["status"] == "completed"
    assert created["end_reason"] == "person_absent"
    assert created["started_at"].startswith("2026-10-08T10:00:00")
    assert created["closed_at"].startswith("2026-10-08T10:00:25")
    assert (
        db_connection.scalar(select(Event.config_snapshot).where(Event.id == event_id))
        == event_payload["config_snapshot"]
    )

    [clip] = created["clips"]
    assert clip["status"] == "ready"
    assert clip["filepath"] == event_payload["video_path"]
    assert clip["size_bytes"] == 4096
    assert clip["source_ready_at"] is not None
    retention = datetime.fromisoformat(clip["expires_at"]) - datetime.fromisoformat(
        clip["created_at"]
    )
    assert abs(retention - timedelta(days=7)) < timedelta(minutes=1)

    # Each request uses a new session, so reads must come from PostgreSQL.
    response = db_client.get(f"{EVENTS_URL}/{event_id}")
    assert response.status_code == 200
    assert response.json() == created
    response = db_client.get(EVENTS_URL)
    assert response.status_code == 200
    assert created in response.json()

    response = db_client.delete(f"{EVENTS_URL}/{event_id}")
    assert response.status_code == 204
    assert response.content == b""
    assert db_connection.scalar(select(Event.id).where(Event.id == event_id)) is None
    assert db_connection.scalar(select(func.count()).where(VideoClip.event_id == event_id)) == 0
    assert db_client.get(f"{EVENTS_URL}/{event_id}").status_code == 404


def test_clip_expiry_uses_system_settings(
    db_client: TestClient, db_connection: Connection, event_payload: dict[str, Any]
) -> None:
    db_connection.execute(update(SystemSettings).values(retention_days=3))

    response = db_client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert response.status_code == 201, response.text
    clip = response.json()["clips"][0]
    retention = datetime.fromisoformat(clip["expires_at"]) - datetime.fromisoformat(
        clip["created_at"]
    )
    assert abs(retention - timedelta(days=3)) < timedelta(minutes=1)


def test_minimal_payload_is_stored_as_pending(
    db_client: TestClient, event_payload: dict[str, Any]
) -> None:
    body = {"camera_id": event_payload["camera_id"], "video_path": event_payload["video_path"]}
    response = db_client.post(EVENTS_URL, json=body, headers=WORKER_HEADERS)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "completed"
    assert created["clips"][0]["status"] == "pending"
    assert created["config_snapshot"]["detection_config"]["region"] is None


def test_interrupted_event(db_client: TestClient, event_payload: dict[str, Any]) -> None:
    event_payload["end_reason"] = "stream_lost"
    response = db_client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "interrupted"
    assert response.json()["end_reason"] == "stream_lost"


def test_unknown_camera(db_client: TestClient, event_payload: dict[str, Any]) -> None:
    event_payload["camera_id"] = "no-such-camera"
    response = db_client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert response.status_code == 404


def test_duplicate_clip_is_a_conflict_and_rolls_back(
    db_client: TestClient, db_connection: Connection, event_payload: dict[str, Any]
) -> None:
    first = db_client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert first.status_code == 201, first.text

    response = db_client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert response.status_code == 409
    assert "INSERT" not in response.text
    camera_id = UUID(first.json()["camera_id"])
    assert (
        db_connection.scalar(
            select(func.count()).select_from(Event).where(Event.camera_id == camera_id)
        )
        == 1
    )


@pytest.mark.parametrize("method", ["get", "delete"])
def test_unknown_event(db_client: TestClient, method: str) -> None:
    response = db_client.request(method, f"{EVENTS_URL}/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"camera_id": " "},
        {"video_path": ""},
        {"clips": []},  # the old client-built shape is rejected, not ignored
        {"started_at": "2026-10-08T10:00:00"},
        {"closed_at": "2026-10-08T10:00:10Z"},
        {"closed_at": None},
        {"end_reason": "bored"},
        {"recorded_end_at": "2026-10-08T09:59:55Z"},
        {"size_bytes": 0},
        {"config_snapshot": {}},
        {
            "config_snapshot": {
                "schema_version": 1,
                "model_ref": "  ",
                "detection_config": {},
                "settings": {},
            }
        },
    ],
)
def test_invalid_event_payload(event_payload: dict[str, Any], changes: dict[str, Any]) -> None:
    event_payload.update(changes)
    with TestClient(app) as client:
        response = client.post(EVENTS_URL, json=event_payload, headers=WORKER_HEADERS)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["get", "delete"])
def test_invalid_event_id(method: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.request(method, f"{EVENTS_URL}/not-a-uuid")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 422
