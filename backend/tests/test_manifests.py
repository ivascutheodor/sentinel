import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.events import EventCreate
from app.services import manifests

EVENTS_URL = f"{get_settings().api_prefix}/events"
WORKER_HEADERS = {"X-API-Key": get_settings().worker_api_key.get_secret_value()}
VIDEO_BYTES = b"pretend this is an H.264 clip"
VIDEO_FILE = "incident_manifest_test.mp4"
MANIFEST_REF = "manifests/incident_manifest_test.json"


def write_manifest(recordings: Path, camera: str, **video_changes: Any) -> None:
    """Writes the manifest the worker would leave next to VIDEO_FILE."""
    video = {
        "file": VIDEO_FILE,
        "size_bytes": len(VIDEO_BYTES),
        "sha256": hashlib.sha256(VIDEO_BYTES).hexdigest(),
        "codec": "h264",
    } | video_changes
    manifest = {"schema_version": 1, "synced": False, "camera_id": camera, "video": video}
    path = recordings / MANIFEST_REF
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def recordings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, camera_name: str) -> Path:
    """A temporary recordings/ folder with one clip and its correct manifest."""
    monkeypatch.setattr(manifests, "RECORDINGS_DIR", tmp_path)
    (tmp_path / VIDEO_FILE).write_bytes(VIDEO_BYTES)
    write_manifest(tmp_path, camera_name)
    return tmp_path


@pytest.fixture
def payload(camera_name: str) -> dict[str, Any]:
    return {
        "camera_id": camera_name,
        "video_path": VIDEO_FILE,
        "started_at": "2026-10-08T10:00:00Z",
        "last_person_seen_at": "2026-10-08T10:00:20Z",
        "closed_at": "2026-10-08T10:00:25Z",
        "recorded_start_at": "2026-10-08T09:59:55Z",
        "recorded_end_at": "2026-10-08T10:00:25Z",
        "size_bytes": len(VIDEO_BYTES),
        "source_manifest_ref": MANIFEST_REF,
    }


def post(client: TestClient, body: dict[str, Any]):
    return client.post(EVENTS_URL, json=body, headers=WORKER_HEADERS)


# --- Database tests -------------------------------------------------------------------


def test_verified_clip_is_ready_with_its_hash(
    db_client: TestClient, recordings: Path, payload: dict[str, Any]
) -> None:
    response = post(db_client, payload)
    assert response.status_code == 201, response.text
    clip = response.json()["clips"][0]
    assert clip["status"] == "ready"
    assert clip["source_manifest_ref"] == MANIFEST_REF
    assert clip["sha256"] == hashlib.sha256(VIDEO_BYTES).hexdigest()


def test_sending_twice_is_a_conflict(
    db_client: TestClient, recordings: Path, payload: dict[str, Any]
) -> None:
    # The sync script relies on this: 409 means "already stored", so it marks the manifest
    # synced instead of creating a second event.
    assert post(db_client, payload).status_code == 201
    assert post(db_client, payload).status_code == 409


def test_without_manifest_gets_a_placeholder(
    db_client: TestClient, recordings: Path, payload: dict[str, Any]
) -> None:
    del payload["source_manifest_ref"]
    response = post(db_client, payload)
    assert response.status_code == 201, response.text
    clip = response.json()["clips"][0]
    assert clip["source_manifest_ref"].startswith("placeholder/")
    assert clip["sha256"] is None


def test_changed_video_is_refused(
    db_client: TestClient, recordings: Path, payload: dict[str, Any]
) -> None:
    # Same size, different content: only the hash can tell.
    (recordings / VIDEO_FILE).write_bytes(VIDEO_BYTES.upper())
    response = post(db_client, payload)
    assert response.status_code == 422
    assert "SHA-256" in response.json()["detail"]


@pytest.mark.parametrize(
    "break_it, message",
    [
        (lambda rec, cam: (rec / MANIFEST_REF).unlink(), "not found"),
        (lambda rec, cam: (rec / VIDEO_FILE).unlink(), "not found on disk"),
        (lambda rec, cam: (rec / MANIFEST_REF).write_text("{not json"), "not valid"),
        (lambda rec, cam: write_manifest(rec, "another-camera"), "belongs to camera"),
        (lambda rec, cam: write_manifest(rec, cam, file="other.mp4"), "not this clip"),
        (lambda rec, cam: write_manifest(rec, cam, size_bytes=999), "size does not match"),
    ],
    ids=[
        "manifest missing",
        "video missing",
        "manifest corrupt",
        "other camera",
        "other file",
        "wrong size",
    ],
)
def test_broken_manifest_is_refused(
    db_client: TestClient,
    recordings: Path,
    payload: dict[str, Any],
    camera_name: str,
    break_it,
    message: str,
) -> None:
    break_it(recordings, camera_name)
    response = post(db_client, payload)
    assert response.status_code == 422
    assert message in response.json()["detail"]


# --- Request validation (no database) -------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        "../secret.json",
        "manifests/../../secret.json",
        "manifests/sub/file.json",
        "manifests\\file.json",
        "other/file.json",
        "manifests/file.txt",
    ],
)
def test_manifest_ref_must_be_a_plain_name_in_manifests(ref: str) -> None:
    with pytest.raises(ValidationError):
        EventCreate(camera_id="cam", video_path="clip.mp4", source_manifest_ref=ref)


def test_manifest_needs_size_and_recorded_times() -> None:
    with pytest.raises(ValidationError, match="needs size_bytes"):
        EventCreate(camera_id="cam", video_path="clip.mp4", source_manifest_ref=MANIFEST_REF)
