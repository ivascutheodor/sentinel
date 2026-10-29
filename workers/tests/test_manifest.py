import hashlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from manifest import (  # noqa: E402
    event_payload,
    find_unsynced,
    load_manifest,
    manifest_ref,
    save_manifest,
    sync_manifest,
    write_manifest,
)
from recorder import Incident  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=UTC)
VIDEO_BYTES = b"pretend this is an H.264 clip"
SNAPSHOT = {"schema_version": 1, "model_ref": "yolo11n.pt", "detection_config": {}, "settings": {}}


def make_incident(clip: Path) -> Incident:
    return Incident(
        clip=clip,
        started_at=T0 + timedelta(seconds=5),
        last_person_seen_at=T0 + timedelta(seconds=20),
        closed_at=T0 + timedelta(seconds=26),
        end_reason="person_absent",
        recorded_start_at=T0,
        recorded_end_at=T0 + timedelta(seconds=25),
        frame_count=750,
    )


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    path = tmp_path / "incident_test.mp4"
    path.write_bytes(VIDEO_BYTES)
    return path


@pytest.fixture
def manifest_file(clip: Path) -> Path:
    return write_manifest(make_incident(clip), "test_camera_01", SNAPSHOT, 30, (464, 832))


class FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class FakePost:
    """Stands in for requests.post and remembers what it was asked to send."""

    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def sync(path: Path, post: FakePost):
    return sync_manifest(path, "http://api.test/api/v1", "secret-key", post=post)


# --- writing --------------------------------------------------------------------------


def test_manifest_is_written_next_to_the_clip(clip: Path, manifest_file: Path) -> None:
    assert manifest_file == clip.parent / "manifests" / "incident_test.json"
    assert manifest_ref(manifest_file) == "manifests/incident_test.json"
    assert not list(manifest_file.parent.glob("*.tmp"))  # the temporary file was renamed

    manifest = load_manifest(manifest_file)
    assert manifest["synced"] is False
    assert manifest["camera_id"] == "test_camera_01"
    assert manifest["video"] == {
        "file": "incident_test.mp4",
        "size_bytes": len(VIDEO_BYTES),
        "sha256": hashlib.sha256(VIDEO_BYTES).hexdigest(),
        "codec": "h264",
        "fps": 30,
        "width": 464,
        "height": 832,
        "frame_count": 750,
    }
    assert manifest["started_at"] == "2026-01-01T00:00:05+00:00"
    assert manifest["config_snapshot"] == SNAPSHOT


def test_payload_comes_from_the_manifest(manifest_file: Path) -> None:
    payload = event_payload(load_manifest(manifest_file), "manifests/incident_test.json")
    assert payload["camera_id"] == "test_camera_01"
    assert payload["video_path"] == "incident_test.mp4"
    assert payload["size_bytes"] == len(VIDEO_BYTES)
    assert payload["source_manifest_ref"] == "manifests/incident_test.json"
    assert "synced" not in payload  # worker bookkeeping, not event data


def test_missing_clip_is_sent_without_manifest(tmp_path: Path) -> None:
    # The writer failed: nothing to verify, so the backend will keep the clip `pending`.
    path = write_manifest(make_incident(tmp_path / "gone.mp4"), "cam", SNAPSHOT, 30, (2, 2))
    payload = event_payload(load_manifest(path), manifest_ref(path))
    assert "source_manifest_ref" not in payload
    assert "size_bytes" not in payload


# --- syncing --------------------------------------------------------------------------


@pytest.mark.parametrize("status, message", [(201, "saved"), (409, "already in the database")])
def test_stored_event_marks_manifest_synced(manifest_file: Path, status: int, message: str):
    post = FakePost(FakeResponse(status))
    result = sync(manifest_file, post)
    assert result.synced and result.message == message
    assert load_manifest(manifest_file)["synced"] is True
    [call] = post.calls
    assert call["url"] == "http://api.test/api/v1/events"
    assert call["headers"] == {"X-API-Key": "secret-key"}


@pytest.mark.parametrize(
    "response",
    [FakeResponse(500, "boom"), FakeResponse(422, "bad"), requests.ConnectionError("down")],
    ids=["server error", "rejected", "backend down"],
)
def test_failed_send_keeps_manifest_unsynced(manifest_file: Path, response) -> None:
    result = sync(manifest_file, FakePost(response))
    assert not result.synced
    assert load_manifest(manifest_file)["synced"] is False


def test_synced_manifest_is_not_sent_again(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    manifest["synced"] = True
    save_manifest(manifest_file, manifest)

    post = FakePost(FakeResponse(201))
    assert sync(manifest_file, post).synced
    assert post.calls == []


def test_find_unsynced(tmp_path: Path) -> None:
    folder = tmp_path / "manifests"
    save_manifest(folder / "a_pending.json", {"synced": False})
    save_manifest(folder / "b_done.json", {"synced": True})
    (folder / "c_broken.json").write_text("{cut off")  # reported, not skipped

    assert [p.name for p in find_unsynced(folder)] == ["a_pending.json", "c_broken.json"]
