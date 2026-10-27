from fastapi.testclient import TestClient

from server.server import app

client = TestClient(app)


def test_user_routes_require_session_cookie() -> None:
    for path in (
        "/api/v1/auth/me",
        "/api/v1/events",
        "/api/v1/events/00000000-0000-0000-0000-000000000000",
        "/api/v1/videos/clip.mp4",
    ):
        assert client.get(path).status_code == 401, path


def test_create_event_requires_worker_key() -> None:
    payload = {"camera_id": "test_camera_01", "video_path": "clip.mp4"}

    assert client.post("/api/v1/events", json=payload).status_code == 401
    response = client.post("/api/v1/events", json=payload, headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
