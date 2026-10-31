from typing import Any
from uuid import uuid4

import pytest
from conftest import API, TEST_PASSWORD, act_as, add_user, login
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select, update

from app.db.enums import UserRole
from app.db.models import AuditLog, User
from app.main import app

USERS_URL = f"{API}/users"
ME_URL = f"{API}/auth/me"
PASSWORD_URL = f"{API}/auth/password"
NEW_PASSWORD = "a brand new passphrase"


def new_user(**changes: Any) -> dict[str, Any]:
    return {
        "username": f"New.User-{uuid4().hex[:8]}",
        "display_name": "New User",
        "password": "temporary password 1",
    } | changes


def actions_on(connection: Connection, user_id: str) -> list[str]:
    return list(
        connection.scalars(
            select(AuditLog.action)
            .where(AuditLog.resource_type == "user", AuditLog.resource_id == str(user_id))
            .order_by(AuditLog.occurred_at)
        ).all()
    )


@pytest.fixture
def client(db_app: None) -> TestClient:
    """No overrides: requests are authenticated by real session cookies."""
    return TestClient(app)


# --- Managing users (admin) ------------------------------------------------------------


def test_admin_creates_lists_and_updates_users(
    db_client: TestClient, db_connection: Connection
) -> None:
    body = new_user(role="admin")
    response = db_client.post(USERS_URL, json=body)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["username"] == body["username"].lower()  # stored the way login looks it up
    assert created["role"] == "admin"
    assert created["is_active"] is True
    assert "password" not in created and "password_hash" not in created

    assert created in db_client.get(USERS_URL).json()

    response = db_client.patch(f"{USERS_URL}/{created['id']}", json={"display_name": "Renamed"})
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Renamed"
    assert actions_on(db_connection, created["id"]) == ["user.create", "user.update"]


def test_new_user_can_log_in(db_client: TestClient, db_app: None) -> None:
    body = new_user()
    db_client.post(USERS_URL, json=body)
    with TestClient(app) as fresh:  # its own cookies; the admin override only skips the check
        response = fresh.post(
            f"{API}/auth/login", json={"username": body["username"], "password": body["password"]}
        )
    assert response.status_code == 200, response.text


def test_duplicate_username(db_client: TestClient) -> None:
    body = new_user()
    assert db_client.post(USERS_URL, json=body).status_code == 201
    # Same name in other letters is the same account: usernames are stored lower-case.
    body["username"] = body["username"].upper()
    assert db_client.post(USERS_URL, json=body).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"password": "too short"},
        {"password": "x" * 1025},
        {"username": "no spaces allowed"},
        {"username": "ab"},
        {"display_name": " "},
        {"role": "superuser"},
        {"is_admin": True},
    ],
)
def test_invalid_new_user(db_client: TestClient, changes: dict[str, Any]) -> None:
    assert db_client.post(USERS_URL, json=new_user(**changes)).status_code == 422


@pytest.mark.parametrize("body", [{"role": None}, {"is_active": None}, {"password_hash": "x"}])
def test_invalid_update(db_client: TestClient, db_connection: Connection, body: dict) -> None:
    user = add_user(db_connection)
    assert db_client.patch(f"{USERS_URL}/{user.id}", json=body).status_code == 422


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "", None),
        ("post", "", new_user()),
        ("patch", "/{id}", {"role": "admin"}),
        ("post", "/{id}/password", {"new_password": NEW_PASSWORD}),
    ],
)
def test_users_cannot_manage_users(
    db_client: TestClient, db_connection: Connection, method: str, path: str, body: Any
) -> None:
    user = add_user(db_connection)
    act_as(user)
    response = db_client.request(method, USERS_URL + path.format(id=user.id), json=body)
    assert response.status_code == 403


def test_unknown_user(db_client: TestClient) -> None:
    assert db_client.patch(f"{USERS_URL}/{uuid4()}", json={"role": "user"}).status_code == 404


# --- Never without an admin ------------------------------------------------------------


@pytest.mark.parametrize("body", [{"role": "user"}, {"is_active": False}])
def test_admin_cannot_remove_own_access(db_client: TestClient, admin: User, body: dict) -> None:
    response = db_client.patch(f"{USERS_URL}/{admin.id}", json=body)
    assert response.status_code == 409
    assert "your own" in response.json()["detail"]


def test_last_active_admin_cannot_be_removed(
    db_client: TestClient, db_connection: Connection, admin: User
) -> None:
    other_admin = add_user(db_connection, UserRole.ADMIN)
    # Simulates the race the row lock prevents: every other admin, including the one making
    # this request, was demoted a moment ago by someone else.
    db_connection.execute(
        update(User)
        .where(User.role == UserRole.ADMIN, User.id != other_admin.id)
        .values(role=UserRole.USER)
    )
    response = db_client.patch(f"{USERS_URL}/{other_admin.id}", json={"role": "user"})
    assert response.status_code == 409
    assert "At least one" in response.json()["detail"]


# --- Changes that log people out -------------------------------------------------------


@pytest.mark.parametrize("body", [{"role": "admin"}, {"is_active": False}])
def test_role_change_or_deactivation_logs_the_user_out(
    client: TestClient, db_connection: Connection, body: dict
) -> None:
    admin = add_user(db_connection, UserRole.ADMIN, with_password=True)
    target = add_user(db_connection, with_password=True)
    target_client = TestClient(app)
    assert login(target_client, target).status_code == 200
    assert login(client, admin).status_code == 200

    response = client.patch(f"{USERS_URL}/{target.id}", json=body)
    assert response.status_code == 200, response.text
    assert target_client.get(ME_URL).status_code == 401

    # Reactivating does not bring the old session back.
    client.patch(f"{USERS_URL}/{target.id}", json={"is_active": True})
    assert target_client.get(ME_URL).status_code == 401


def test_display_name_change_keeps_sessions(client: TestClient, db_connection: Connection) -> None:
    admin = add_user(db_connection, UserRole.ADMIN, with_password=True)
    target = add_user(db_connection, with_password=True)
    target_client = TestClient(app)
    login(target_client, target)
    login(client, admin)
    client.patch(f"{USERS_URL}/{target.id}", json={"display_name": "Still Logged In"})
    assert target_client.get(ME_URL).status_code == 200


def test_admin_password_reset(client: TestClient, db_connection: Connection) -> None:
    admin = add_user(db_connection, UserRole.ADMIN, with_password=True)
    target = add_user(db_connection, with_password=True)
    target_client = TestClient(app)
    login(target_client, target)
    login(client, admin)

    response = client.post(f"{USERS_URL}/{target.id}/password", json={"new_password": NEW_PASSWORD})
    assert response.status_code == 204, response.text
    assert target_client.get(ME_URL).status_code == 401
    assert login(TestClient(app), target).status_code == 401
    assert login(TestClient(app), target, NEW_PASSWORD).status_code == 200
    assert "user.password_reset" in actions_on(db_connection, target.id)

    # Your own password goes through /auth/password, which asks for the current one.
    response = client.post(f"{USERS_URL}/{admin.id}/password", json={"new_password": NEW_PASSWORD})
    assert response.status_code == 409


# --- Changing your own password --------------------------------------------------------


def test_change_own_password(client: TestClient, db_connection: Connection) -> None:
    user = add_user(db_connection, with_password=True)
    other_device = TestClient(app)
    login(client, user)
    login(other_device, user)

    wrong = {"current_password": "not my password", "new_password": NEW_PASSWORD}
    response = client.post(PASSWORD_URL, json=wrong)
    assert response.status_code == 400  # not 401: this session is still fine
    assert client.get(ME_URL).status_code == 200

    right = {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
    assert client.post(PASSWORD_URL, json=right).status_code == 204
    assert client.get(ME_URL).status_code == 200  # this session stays
    assert other_device.get(ME_URL).status_code == 401  # every other one is logged out
    assert login(TestClient(app), user, NEW_PASSWORD).status_code == 200

    outcomes = db_connection.scalars(
        select(AuditLog.outcome)
        .where(AuditLog.action == "user.password_change", AuditLog.actor_user_id == user.id)
        .order_by(AuditLog.occurred_at)
    ).all()
    assert [str(outcome) for outcome in outcomes] == ["denied", "success"]


@pytest.mark.parametrize(
    "body",
    [
        {"current_password": TEST_PASSWORD, "new_password": "short"},
        {"current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD},
    ],
    ids=["too short", "unchanged"],
)
def test_invalid_new_password(client: TestClient, db_connection: Connection, body: dict) -> None:
    user = add_user(db_connection, with_password=True)
    login(client, user)
    assert client.post(PASSWORD_URL, json=body).status_code == 422


def test_change_password_requires_login() -> None:
    body = {"current_password": "x", "new_password": NEW_PASSWORD}
    assert TestClient(app).post(PASSWORD_URL, json=body).status_code == 401
