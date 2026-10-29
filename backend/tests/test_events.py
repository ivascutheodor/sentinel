from datetime import UTC, datetime, timedelta
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

    assert created["camera_name"] == event_payload["camera_id"]

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
    response = db_client.get(EVENTS_URL, params={"camera_id": created["camera_id"]})
    assert response.status_code == 200
    assert response.json() == {"items": [created], "total": 1, "limit": 50, "offset": 0}

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


def post_event_at(
    client: TestClient, payload: dict[str, Any], started_at: datetime, camera: str | None = None
) -> dict[str, Any]:
    """Posts an event whose times all start at `started_at`; returns the response body."""
    times = {
        "started_at": started_at,
        "last_person_seen_at": started_at + timedelta(seconds=20),
        "closed_at": started_at + timedelta(seconds=25),
        "recorded_start_at": started_at - timedelta(seconds=5),
        "recorded_end_at": started_at + timedelta(seconds=25),
    }
    body = {
        **payload,
        **{key: value.isoformat() for key, value in times.items()},
        "video_path": f"incident_{uuid4().hex}.mp4",
        "camera_id": camera or payload["camera_id"],
    }
    response = client.post(EVENTS_URL, json=body, headers=WORKER_HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


T0 = datetime(2026, 10, 8, 10, tzinfo=UTC)


def test_list_pages_newest_first(db_client: TestClient, event_payload: dict[str, Any]) -> None:
    # Posted out of order, so the order can only come from `started_at`, not `created_at`.
    ids = {}
    for minutes in [2, 0, 4, 1, 3]:
        ids[minutes] = post_event_at(db_client, event_payload, T0 + timedelta(minutes=minutes))[
            "id"
        ]
    camera_id = db_client.get(f"{EVENTS_URL}/{ids[0]}").json()["camera_id"]

    pages = [
        db_client.get(
            EVENTS_URL, params={"camera_id": camera_id, "limit": 2, "offset": offset}
        ).json()
        for offset in (0, 2, 4)
    ]
    assert [page["total"] for page in pages] == [5, 5, 5]
    assert [page["limit"] for page in pages] == [2, 2, 2]
    assert [page["offset"] for page in pages] == [0, 2, 4]
    assert [[event["id"] for event in page["items"]] for page in pages] == [
        [ids[4], ids[3]],
        [ids[2], ids[1]],
        [ids[0]],
    ]
    assert pages[0]["items"][0]["camera_name"] == event_payload["camera_id"]


def test_list_filters_by_camera(
    db_client: TestClient, db_connection: Connection, event_payload: dict[str, Any]
) -> None:
    other = f"other-{uuid4().hex}"
    db_connection.execute(insert(Camera).values(name=other, stream_url=f"rtsp://{other}/s"))
    mine = post_event_at(db_client, event_payload, T0)
    theirs = post_event_at(db_client, event_payload, T0, camera=other)

    for event in (mine, theirs):
        page = db_client.get(EVENTS_URL, params={"camera_id": event["camera_id"]}).json()
        assert page["total"] == 1
        assert [item["id"] for item in page["items"]] == [event["id"]]

    page = db_client.get(EVENTS_URL, params={"camera_id": str(uuid4())}).json()
    assert page == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_filters_by_start_time(db_client: TestClient, event_payload: dict[str, Any]) -> None:
    events = [
        post_event_at(db_client, event_payload, T0 + timedelta(hours=hours)) for hours in range(4)
    ]
    params = {
        "camera_id": events[0]["camera_id"],
        # from is inclusive, to is exclusive: hours 1 and 2, not 3
        "started_from": (T0 + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "started_to": (T0 + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
    }
    page = db_client.get(EVENTS_URL, params=params).json()
    assert page["total"] == 2
    assert [item["id"] for item in page["items"]] == [events[2]["id"], events[1]["id"]]

    # Another timezone is the same instant: 13:00+02:00 is 11:00Z, so only hour 0 is left.
    # `params=` encodes `+` as %2B; typed raw into a URL it would turn into a space.
    params = {"camera_id": events[0]["camera_id"], "started_to": "2026-10-08T13:00:00+02:00"}
    page = db_client.get(EVENTS_URL, params=params).json()
    assert [item["id"] for item in page["items"]] == [events[0]["id"]]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"camera_id": "not-a-uuid"},
        {"started_from": "2026-10-08T10:00:00"},  # no timezone
        {"started_from": "2026-10-08T10:00:00Z", "started_to": "2026-10-08T10:00:00Z"},
        {"started_from": "2026-10-08T11:00:00Z", "started_to": "2026-10-08T10:00:00Z"},
    ],
)
def test_list_rejects_bad_parameters(params: dict[str, Any]) -> None:
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get(EVENTS_URL, params=params)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 422, response.text


def test_list_requires_login() -> None:
    with TestClient(app) as client:
        assert client.get(EVENTS_URL).status_code == 401


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
