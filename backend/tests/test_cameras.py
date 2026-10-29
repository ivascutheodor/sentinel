from typing import Any
from uuid import uuid4

import pytest
from conftest import API, act_as, add_user
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select

from app.db.models import AuditLog, Camera

CAMERAS_URL = f"{API}/cameras"


def new_camera(**changes: Any) -> dict[str, Any]:
    name = f"cam-{uuid4().hex[:8]}"
    return {"name": name, "stream_url": f"rtsp://10.0.0.5:554/{name}"} | changes


ZONE = {"region": {"points": [[172, 423], [363, 430], [367, 813], [172, 797]]}}


def test_admin_creates_reads_and_updates_a_camera(
    db_client: TestClient, db_connection: Connection
) -> None:
    body = new_camera(location="Pharmacy", detection_config=ZONE)
    response = db_client.post(CAMERAS_URL, json=body)
    assert response.status_code == 201, response.text
    camera = response.json()
    assert camera["is_enabled"] is False  # the database default: monitoring is opt-in
    assert camera["detection_config"] == {
        "schema_version": 1,
        "region": {
            "type": "polygon",
            "points": ZONE["region"]["points"],
            "match_rule": "bottom_center",
        },
    }
    assert db_client.get(f"{CAMERAS_URL}/{camera['id']}").json() == camera

    # Only the fields sent change; `null` clears an optional one.
    response = db_client.patch(
        f"{CAMERAS_URL}/{camera['id']}", json={"is_enabled": True, "location": None}
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["is_enabled"] is True
    assert updated["location"] is None
    assert updated["name"] == body["name"]

    actions = db_connection.scalars(
        select(AuditLog.action)
        .where(AuditLog.resource_id == camera["id"])
        .order_by(AuditLog.occurred_at)
    ).all()
    assert actions == ["camera.create", "camera.update"]


def test_everyone_logged_in_lists_cameras_without_stream_urls(
    db_client: TestClient, db_connection: Connection, camera_name: str
) -> None:
    act_as(add_user(db_connection))
    response = db_client.get(CAMERAS_URL)
    assert response.status_code == 200
    [camera] = [c for c in response.json() if c["name"] == camera_name]
    assert set(camera) == {"id", "name", "location", "is_enabled", "last_frame_at"}


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "", new_camera()),
        ("patch", "/{id}", {"is_enabled": True}),
        ("get", "/{id}", None),
    ],
)
def test_users_cannot_manage_cameras(
    db_client: TestClient,
    db_connection: Connection,
    camera_name: str,
    method: str,
    path: str,
    body: Any,
) -> None:
    camera_id = db_connection.scalar(select(Camera.id).where(Camera.name == camera_name))
    act_as(add_user(db_connection))
    response = db_client.request(method, CAMERAS_URL + path.format(id=camera_id), json=body)
    assert response.status_code == 403


def test_names_are_unique_ignoring_case(db_client: TestClient, camera_name: str) -> None:
    response = db_client.post(CAMERAS_URL, json=new_camera(name=camera_name.upper()))
    assert response.status_code == 409


def test_stream_urls_are_unique(db_client: TestClient, camera_name: str) -> None:
    body = new_camera(stream_url=f"rtsp://{camera_name}/stream")  # the test camera's URL
    assert db_client.post(CAMERAS_URL, json=body).status_code == 409


def test_renaming_into_a_taken_name_is_a_conflict(db_client: TestClient, camera_name: str) -> None:
    camera = db_client.post(CAMERAS_URL, json=new_camera()).json()
    response = db_client.patch(f"{CAMERAS_URL}/{camera['id']}", json={"name": camera_name})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "  "},
        {"stream_url": "http://10.0.0.5/stream"},
        {"stream_url": "rtsp://user:secret@10.0.0.5/stream"},  # no passwords in the URL
        {"credentials_ref": "Has-Capitals"},
        {"detection_config": {"region": {"points": [[1, 1], [2, 2]]}}},  # 3 points minimum
        {"detection_config": {"region": {"points": [[1, 1]] * 17}}},  # 16 maximum
        {"detection_config": {"region": {"points": [[-1, 1], [2, 2], [3, 3]]}}},
        {"detection_config": {"region": None, "extra": 1}},
        {"unknown": "field"},
    ],
)
def test_invalid_camera(db_client: TestClient, changes: dict[str, Any]) -> None:
    assert db_client.post(CAMERAS_URL, json=new_camera(**changes)).status_code == 422


@pytest.mark.parametrize("field", ["name", "stream_url", "is_enabled", "detection_config"])
def test_required_fields_cannot_be_cleared(
    db_client: TestClient, db_connection: Connection, camera_name: str, field: str
) -> None:
    camera_id = db_connection.scalar(select(Camera.id).where(Camera.name == camera_name))
    response = db_client.patch(f"{CAMERAS_URL}/{camera_id}", json={field: None})
    assert response.status_code == 422


def test_unknown_camera(db_client: TestClient) -> None:
    assert db_client.get(f"{CAMERAS_URL}/{uuid4()}").status_code == 404
    assert db_client.patch(f"{CAMERAS_URL}/{uuid4()}", json={"is_enabled": True}).status_code == 404
