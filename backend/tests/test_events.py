import os
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, func, insert, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Camera, Event, VideoClip
from app.db.session import get_session
from app.main import app

EVENTS_URL = f"{get_settings().api_prefix}/events"


@pytest.fixture
def event_payload() -> dict[str, Any]:
    return {
        "camera_id": str(uuid4()),
        "started_at": "2026-10-08T10:00:00Z",
        "last_person_seen_at": "2026-10-08T10:00:20Z",
        "config_snapshot": {
            "schema_version": 1,
            "model_ref": "test-model-v1",
            "detection_config": {"schema_version": 1, "region": None},
            "settings": {"retention_days": 7, "post_roll_seconds": 10},
        },
    }


@pytest.fixture
def ready_clip() -> dict[str, Any]:
    clip_key = uuid4().hex
    return {
        "part_number": 1,
        "source_manifest_ref": f"manifests/{clip_key}.json",
        "status": "ready",
        "filepath": f"recordings/{clip_key}.mp4",
        "size_bytes": 4096,
        "recorded_start_at": "2026-10-08T09:59:50Z",
        "recorded_end_at": "2026-10-08T10:00:30Z",
        "source_ready_at": "2026-10-08T10:00:31Z",
        "expires_at": "2026-10-15T10:00:30Z",
    }


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def db_client(db_connection: Connection, event_payload: dict[str, Any]) -> Iterator[TestClient]:
    camera_id = UUID(event_payload["camera_id"])
    db_connection.execute(
        insert(Camera).values(
            id=camera_id,
            name="API integration test camera",
            stream_url=f"rtsp://test-camera-{camera_id.hex}/stream",
        )
    )

    def override_session() -> Iterator[Session]:
        # Request commits release a savepoint; the outer test transaction is rolled back.
        with Session(bind=db_connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_create_read_and_delete_event(
    db_client: TestClient, db_connection: Connection, event_payload: dict[str, Any]
) -> None:
    response = db_client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 201, response.text
    created = response.json()
    event_id = UUID(created["id"])
    assert created["camera_id"] == event_payload["camera_id"]
    assert created["status"] == "capturing"
    assert created["created_at"]
    assert created["clips"] == []
    assert (
        db_connection.scalar(select(Event.config_snapshot).where(Event.id == event_id))
        == (event_payload["config_snapshot"])
    )

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
    assert db_client.get(f"{EVENTS_URL}/{event_id}").status_code == 404


def test_create_completed_event_with_clip(
    db_client: TestClient,
    db_connection: Connection,
    event_payload: dict[str, Any],
    ready_clip: dict[str, Any],
) -> None:
    event_payload.update(
        status="completed",
        closed_at="2026-10-08T10:00:30Z",
        end_reason="person_absent",
        clips=[ready_clip],
    )
    response = db_client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "completed"
    clip = created["clips"][0]
    assert clip["event_id"] == created["id"]
    assert clip["filepath"] == ready_clip["filepath"]
    assert clip["status"] == "ready"
    assert (
        db_connection.scalar(select(VideoClip.filepath).where(VideoClip.id == UUID(clip["id"])))
        == ready_clip["filepath"]
    )
    assert db_client.get(f"{EVENTS_URL}/{created['id']}").json() == created

    # Existing NO ACTION foreign keys protect events referenced by clips.
    response = db_client.delete(f"{EVENTS_URL}/{created['id']}")
    assert response.status_code == 409
    assert db_client.get(f"{EVENTS_URL}/{created['id']}").json() == created


def test_unknown_camera(db_client: TestClient, event_payload: dict[str, Any]) -> None:
    event_payload["camera_id"] = str(uuid4())
    response = db_client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Camera not found."


@pytest.mark.parametrize("method", ["get", "delete"])
def test_unknown_event(db_client: TestClient, method: str) -> None:
    response = db_client.request(method, f"{EVENTS_URL}/{uuid4()}")
    assert response.status_code == 404


def test_duplicate_capturing_event(db_client: TestClient, event_payload: dict[str, Any]) -> None:
    first = db_client.post(EVENTS_URL, json=event_payload)
    assert first.status_code == 201
    response = db_client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 409
    assert "INSERT" not in response.text
    assert db_client.delete(f"{EVENTS_URL}/{first.json()['id']}").status_code == 204
    assert db_client.post(EVENTS_URL, json=event_payload).status_code == 201


def test_clip_conflict_rolls_back_entire_event(
    db_client: TestClient, db_connection: Connection, event_payload: dict[str, Any]
) -> None:
    clip = {
        "part_number": 1,
        "source_manifest_ref": f"manifests/{uuid4().hex}.json",
        "expires_at": "2026-10-15T10:00:30Z",
    }
    event_payload["clips"] = [clip, {**clip, "part_number": 2}]
    response = db_client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 409
    assert (
        db_connection.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.camera_id == UUID(event_payload["camera_id"]))
        )
        == 0
    )
    assert (
        db_connection.scalar(
            select(func.count())
            .select_from(VideoClip)
            .where(VideoClip.source_manifest_ref == clip["source_manifest_ref"])
        )
        == 0
    )

    event_payload["clips"] = [clip]
    response = db_client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 201, response.text
    assert response.json()["clips"][0]["status"] == "pending"


@pytest.mark.parametrize(
    "changes",
    [
        {"camera_id": "test_camera_01"},
        {"video_path": "old-payload.mp4"},
        {"started_at": "2026-10-08T10:00:00"},
        {"last_person_seen_at": "2026-10-08T09:00:00Z"},
        {"status": "capturing", "closed_at": "2026-10-08T10:00:30Z"},
        {"status": "capturing", "end_reason": "manual_stop"},
        {"status": "completed"},
        {"status": "completed", "closed_at": "2026-10-08T10:00:30Z", "end_reason": "manual_stop"},
        {
            "status": "interrupted",
            "closed_at": "2026-10-08T10:00:30Z",
            "end_reason": "person_absent",
        },
        {"status": "completed", "closed_at": "2026-10-08T10:00:10Z", "end_reason": "person_absent"},
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
        response = client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"filepath": None},
        {"source_manifest_ref": " "},
        {"size_bytes": 0},
        {"recorded_end_at": "2026-10-08T09:59:50Z"},
        {"recorded_start_at": None},
        {"source_ready_at": None},
        {"expires_at": "2026-10-15T10:00:30"},
        {"sha256": "invalid"},
    ],
)
def test_invalid_clip_payload(
    event_payload: dict[str, Any], ready_clip: dict[str, Any], changes: dict[str, Any]
) -> None:
    ready_clip.update(changes)
    event_payload["clips"] = [ready_clip]
    with TestClient(app) as client:
        response = client.post(EVENTS_URL, json=event_payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("method", ["get", "delete"])
def test_invalid_event_id(method: str) -> None:
    with TestClient(app) as client:
        response = client.request(method, f"{EVENTS_URL}/not-a-uuid")
    assert response.status_code == 422
