import itertools
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from conftest import API, TEST_PASSWORD, add_user, login
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, insert, select

from app.db.enums import AuditOutcome
from app.db.models import AuditLog, User
from app.main import app
from app.services.login_throttle import (
    FAILED_LOGIN,
    LOGIN_WINDOW,
    MAX_FAILURES_PER_IP,
    MAX_FAILURES_PER_USERNAME,
    THROTTLED_LOGIN,
)

LOGIN_URL = f"{API}/auth/login"
WRONG = "wrong password, again"


def client_from(ip: str) -> TestClient:
    """A client whose requests come from `ip` (TestClient's default is not an IP address)."""
    return TestClient(app, client=(ip, 50000))


_next_ip = itertools.count(1)


def new_ip() -> str:
    """A fresh address each call. 198.51.100.0/24 is reserved for documentation, so it
    can't clash with a real client's failed logins in the database."""
    return f"198.51.100.{next(_next_ip) % 254 + 1}"


@pytest.fixture
def user(db_app: None, db_connection: Connection) -> User:
    return add_user(db_connection, with_password=True)


def fail(client: TestClient, username: str, times: int) -> None:
    for _ in range(times):
        response = client.post(LOGIN_URL, json={"username": username, "password": WRONG})
        assert response.status_code == 401, response.text


def test_username_is_blocked_after_five_failures(user: User, db_connection: Connection) -> None:
    client = client_from(new_ip())
    fail(client, user.username, MAX_FAILURES_PER_USERNAME)

    # Even the right password is refused while blocked.
    response = login(client, user)
    assert response.status_code == 429
    retry_after = int(response.headers["Retry-After"])
    assert 0 < retry_after <= LOGIN_WINDOW.total_seconds()

    # From another address too: the limit protects the account, not just one attacker.
    assert login(client_from(new_ip()), user).status_code == 429

    # Blocked attempts are audited, but separately, so they don't extend the block.
    refused = db_connection.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == THROTTLED_LOGIN,
            AuditLog.details["username"].astext == user.username,
        )
    )
    assert refused == 2


def test_unknown_username_gets_the_same_429(db_app: None) -> None:
    # Otherwise a 429 (or its absence) would reveal which usernames are real.
    client = client_from(new_ip())
    username = f"nobody-{uuid4().hex[:8]}"
    fail(client, username, MAX_FAILURES_PER_USERNAME)
    response = client.post(LOGIN_URL, json={"username": username, "password": WRONG})
    assert response.status_code == 429


def test_old_failures_do_not_count(user: User, db_connection: Connection) -> None:
    # Five failures from just over 15 minutes ago, as the login would have written them.
    long_ago = datetime.now(UTC) - LOGIN_WINDOW - timedelta(seconds=5)
    for _ in range(MAX_FAILURES_PER_USERNAME):
        db_connection.execute(
            insert(AuditLog).values(
                actor_type="anonymous",
                action=FAILED_LOGIN,
                outcome=AuditOutcome.DENIED,
                occurred_at=long_ago,
                details={"username": user.username, "ip": None},
            )
        )
    assert login(client_from(new_ip()), user).status_code == 200


def test_success_below_the_limit(user: User) -> None:
    client = client_from(new_ip())
    fail(client, user.username, MAX_FAILURES_PER_USERNAME - 1)
    assert login(client, user, TEST_PASSWORD).status_code == 200


def test_one_address_is_blocked_after_twenty_failures(user: User) -> None:
    client = client_from(new_ip())
    # Spread over different usernames, so the per-username limit is never reached.
    for i in range(MAX_FAILURES_PER_IP):
        fail(client, f"guess-{i}-{uuid4().hex[:6]}", 1)

    assert login(client, user).status_code == 429  # a real account, from the same address
    assert login(client_from(new_ip()), user).status_code == 200  # other addresses are fine
