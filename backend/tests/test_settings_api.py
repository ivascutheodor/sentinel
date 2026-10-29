from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from conftest import API, act_as, add_user
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select

from app.core.config import get_settings
from app.db.models import AuditLog, SystemSettings, User

SETTINGS_URL = f"{API}/settings"


def test_admin_reads_settings(db_client: TestClient) -> None:
    response = db_client.get(SETTINGS_URL)
    assert response.status_code == 200
    assert response.json()["retention_days"] == 7


def test_admin_changes_settings(
    db_client: TestClient, db_connection: Connection, admin: User
) -> None:
    response = db_client.patch(SETTINGS_URL, json={"retention_days": 30, "pre_roll_seconds": 5})
    assert response.status_code == 200, response.text
    assert response.json()["retention_days"] == 30
    assert db_connection.scalar(select(SystemSettings.retention_days)) == 30

    details, actor = db_connection.execute(
        select(AuditLog.details, AuditLog.actor_user_id).where(
            AuditLog.action == "settings.update", AuditLog.actor_user_id == admin.id
        )
    ).one()
    assert actor == admin.id
    assert details == {"changes": {"retention_days": [7, 30], "pre_roll_seconds": [10, 5]}}


def test_unchanged_values_are_not_audited(
    db_client: TestClient, db_connection: Connection, admin: User
) -> None:
    assert db_client.patch(SETTINGS_URL, json={"retention_days": 7}).status_code == 200
    audited = db_connection.scalar(
        select(AuditLog.id).where(
            AuditLog.action == "settings.update", AuditLog.actor_user_id == admin.id
        )
    )
    assert audited is None


def test_retention_change_applies_to_new_clips(db_client: TestClient, camera_name: str) -> None:
    db_client.patch(SETTINGS_URL, json={"retention_days": 2})

    body = {"camera_id": camera_name, "video_path": f"retention_{uuid4().hex}.mp4"}
    worker = {"X-API-Key": get_settings().worker_api_key.get_secret_value()}
    clip = db_client.post(f"{API}/events", json=body, headers=worker).json()["clips"][0]
    retention = datetime.fromisoformat(clip["expires_at"]) - datetime.fromisoformat(
        clip["created_at"]
    )
    assert abs(retention - timedelta(days=2)) < timedelta(minutes=1)


@pytest.mark.parametrize(
    "body",
    [
        {"session_idle_seconds": 50_000},  # more than the stored absolute limit (43200)
        {"session_absolute_seconds": 600},  # less than the stored idle limit (1800)
        {"session_absolute_seconds": 600, "session_idle_seconds": 900},
    ],
)
def test_idle_cannot_exceed_absolute(db_client: TestClient, body: dict[str, Any]) -> None:
    response = db_client.patch(SETTINGS_URL, json=body)
    assert response.status_code == 422
    assert "must not exceed" in response.json()["detail"]


def test_both_session_limits_can_be_lowered_together(db_client: TestClient) -> None:
    body = {"session_absolute_seconds": 600, "session_idle_seconds": 300}
    assert db_client.patch(SETTINGS_URL, json=body).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"retention_days": 0},
        {"retention_days": 3651},
        {"pre_roll_seconds": -1},
        {"clip_part_seconds": 0},
        {"confidence_threshold": 1.5},
        {"session_idle_seconds": None},
        {"id": 2},
    ],
)
def test_invalid_settings(db_client: TestClient, body: dict[str, Any]) -> None:
    assert db_client.patch(SETTINGS_URL, json=body).status_code == 422


@pytest.mark.parametrize("method", ["get", "patch"])
def test_users_cannot_see_or_change_settings(
    db_client: TestClient, db_connection: Connection, method: str
) -> None:
    act_as(add_user(db_connection))
    response = db_client.request(method, SETTINGS_URL, json={"retention_days": 1})
    assert response.status_code == 403
