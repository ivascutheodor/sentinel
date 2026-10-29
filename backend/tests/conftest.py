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
from app.db.models import Camera  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402


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


@pytest.fixture
def db_client(db_app: None, db_connection: Connection, camera_name: str) -> Iterator[TestClient]:
    """A logged-in client with one test camera; everything is rolled back afterwards."""
    db_connection.execute(
        insert(Camera).values(name=camera_name, stream_url=f"rtsp://{camera_name}/stream")
    )
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
