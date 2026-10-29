import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, insert
from sqlalchemy.orm import Session

# Set before `app` is imported: real environment variables win over .env, and "test" skips
# the development camera seed, so tests that never touch the database don't need one.
os.environ["ENVIRONMENT"] = "test"

from app.api.deps import get_current_user  # noqa: E402
from app.core import storage  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.enums import UserRole  # noqa: E402
from app.db.models import Camera, User  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402

API = get_settings().api_prefix
TEST_PASSWORD = "correct horse battery"


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    """A PostgreSQL connection inside a transaction that is rolled back after the test."""
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
def db_app(db_connection: Connection) -> Iterator[None]:
    """Makes the app's requests use `db_connection`, so their writes are rolled back too."""

    def override_session() -> Iterator[Session]:
        # Request commits release a savepoint; the outer test transaction is rolled back.
        with Session(bind=db_connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def camera_name() -> str:
    return f"test-camera-{uuid4().hex}"


def add_user(
    connection: Connection, role: UserRole = UserRole.USER, *, with_password: bool = False
) -> User:
    """Inserts a user (rolled back with the test) and returns it as the routes would see it.

    Hashing is slow, so only users that log in for real get a real password hash.
    """
    values = {
        "username": f"test-{uuid4().hex[:16]}",
        "display_name": "Test User",
        "role": role,
        "password_hash": hash_password(TEST_PASSWORD) if with_password else "not-a-real-hash",
    }
    user_id = connection.scalar(insert(User).values(**values).returning(User.id))
    return User(id=user_id, is_active=True, **values)


def act_as(user: User) -> None:
    """Makes the app treat every request as coming from `user`, skipping the cookie check.

    `db_client` removes the override when the test ends.
    """
    app.dependency_overrides[get_current_user] = lambda: user


def login(client: TestClient, user: User, password: str = TEST_PASSWORD):
    return client.post(f"{API}/auth/login", json={"username": user.username, "password": password})


@pytest.fixture
def admin(db_connection: Connection) -> User:
    return add_user(db_connection, UserRole.ADMIN)


@pytest.fixture
def recordings(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """An empty, temporary recordings/ folder for routes that read or delete files."""
    monkeypatch.setattr(storage, "RECORDINGS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def db_client(
    db_app: None, db_connection: Connection, camera_name: str, admin: User
) -> Iterator[TestClient]:
    """A client logged in as an admin, with one test camera; all rolled back afterwards.

    Call `act_as(other_user)` inside a test to continue as someone else.
    """
    db_connection.execute(
        insert(Camera).values(name=camera_name, stream_url=f"rtsp://{camera_name}/stream")
    )
    act_as(admin)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
