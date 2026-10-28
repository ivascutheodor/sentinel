from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import SystemSettings, User, UserSession
from app.main import app

AUTH_URL = f"{get_settings().api_prefix}/auth"
USERNAME = "settings_test_user"
PASSWORD = "settings-test-password"

# The test database may hold real sessions too; only touch the test user's.
TEST_USER_SESSIONS = UserSession.user_id == (
    select(User.id).where(User.username == USERNAME).scalar_subquery()
)


@pytest.fixture
def client(db_app: None, db_connection: Connection) -> Iterator[TestClient]:
    """A client with one user, everything inside the rolled-back test transaction."""
    db_connection.execute(
        insert(User).values(
            username=USERNAME,
            display_name="Settings Test",
            password_hash=hash_password(PASSWORD),
        )
    )
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> None:
    response = client.post(f"{AUTH_URL}/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200, response.text


def test_migration_seeds_defaults(db_connection: Connection) -> None:
    row = db_connection.execute(select(SystemSettings)).one()
    assert row.id == 1
    assert row.retention_days == 7
    assert row.session_absolute_seconds == 43200
    assert row.session_idle_seconds == 1800


@pytest.mark.parametrize(
    "statement",
    [delete(SystemSettings), text("TRUNCATE system_settings")],
    ids=["delete", "truncate"],
)
def test_row_cannot_be_removed(db_connection: Connection, statement) -> None:
    with pytest.raises(DBAPIError, match="cannot be removed"):
        with db_connection.begin_nested():  # roll back only this statement
            db_connection.execute(statement)
    assert db_connection.scalar(select(SystemSettings.id)) == 1


def test_login_uses_session_lifetime(client: TestClient, db_connection: Connection) -> None:
    # The table's CHECK requires idle <= absolute, so lower both.
    db_connection.execute(
        update(SystemSettings).values(session_absolute_seconds=600, session_idle_seconds=300)
    )

    login(client)

    created_at, expires_at = db_connection.execute(
        select(UserSession.created_at, UserSession.expires_at).where(TEST_USER_SESSIONS)
    ).one()
    assert expires_at - created_at == timedelta(seconds=600)
    assert client.cookies.get(get_settings().session_cookie_name)


def test_idle_timeout_uses_system_settings(client: TestClient, db_connection: Connection) -> None:
    def make_idle_for_ten_minutes() -> None:
        # A successful request refreshes `last_seen_at`, so this is repeated before each check.
        ten_minutes_ago = datetime.now(UTC) - timedelta(minutes=10)
        db_connection.execute(
            update(UserSession)
            .where(TEST_USER_SESSIONS)
            .values(created_at=ten_minutes_ago, last_seen_at=ten_minutes_ago)
        )

    login(client)

    make_idle_for_ten_minutes()
    assert client.get(f"{AUTH_URL}/me").status_code == 200  # default idle limit: 30 minutes

    db_connection.execute(update(SystemSettings).values(session_idle_seconds=300))
    make_idle_for_ten_minutes()
    assert client.get(f"{AUTH_URL}/me").status_code == 401  # 10 minutes > new 5-minute limit
