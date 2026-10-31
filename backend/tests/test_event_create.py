import pytest
from pydantic import ValidationError

from app.schemas.events import EventCreate

FULL_EVENT = {
    "camera_id": "test_camera_01",
    "video_path": "incident.mp4",
    "started_at": "2026-10-26T20:00:05Z",
    "last_person_seen_at": "2026-10-26T20:00:20Z",
    "closed_at": "2026-10-26T20:00:25Z",
    "recorded_start_at": "2026-10-26T20:00:00Z",
    "recorded_end_at": "2026-10-26T20:00:25Z",
    "size_bytes": 123456,
    "config_snapshot": {
        "schema_version": 1,
        "model_ref": "yolo11n.pt",
        "detection_config": {"schema_version": 1, "region": None},
        "settings": {},
    },
}


def test_old_two_field_body_is_still_accepted() -> None:
    event = EventCreate(camera_id="test_camera_01", video_path="incident.mp4")

    assert event.started_at is None
    assert event.end_reason == "person_absent"


def test_full_body_is_accepted() -> None:
    event = EventCreate(**FULL_EVENT)

    assert event.size_bytes == 123456
    assert event.config_snapshot.model_ref == "yolo11n.pt"


@pytest.mark.parametrize(
    "changes",
    [
        {"closed_at": "2026-10-26T20:00:10Z"},  # closed before the person was last seen
        {"recorded_end_at": "2026-10-26T20:00:00Z"},  # zero-length clip
        {"closed_at": None},  # incomplete group of event times
        {"recorded_end_at": None},  # start without end
        {"started_at": "2026-10-26T20:00:05"},  # no timezone
        {"size_bytes": 0},
        {"end_reason": "bored"},
        {"config_snapshot": {"model_ref": "", "detection_config": {}, "settings": {}}},
    ],
)
def test_invalid_bodies_are_rejected(changes: dict) -> None:
    with pytest.raises(ValidationError):
        EventCreate(**(FULL_EVENT | changes))
