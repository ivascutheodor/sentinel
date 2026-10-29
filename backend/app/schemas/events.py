from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from app.db.enums import CaptureState, EventType, VideoStatus
from app.schemas.manifests import ManifestRef

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
EndReason = Literal[
    "person_absent",
    "stream_lost",
    "worker_restart",
    "manual_stop",
    "camera_disabled",
    "inference_stalled",
    "recording_failed",
]


class ConfigSnapshot(BaseModel):
    """Mirrors the `events.config_snapshot` CHECK, so a bad snapshot is a 422, not a 500."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    model_ref: NonBlank
    detection_config: dict[str, JsonValue]
    settings: dict[str, JsonValue]


class EventCreate(BaseModel):
    """What the worker posts once a clip is finished.

    The backend owns the rest: event status from `end_reason`, clip status from whether the
    file's size and time span are known, and `expires_at`. With `source_manifest_ref` the
    clip is verified against the worker's manifest and its SHA-256 is stored.
    """

    model_config = ConfigDict(extra="forbid")

    camera_id: NonBlank  # the camera's name, e.g. "test_camera_01"
    video_path: NonBlank  # file name inside recordings/

    # Optional so a worker that only sends the two fields above still works; the
    # backend then falls back to "now" and leaves the clip `pending`.
    started_at: AwareDatetime | None = None
    last_person_seen_at: AwareDatetime | None = None
    closed_at: AwareDatetime | None = None
    end_reason: EndReason = "person_absent"
    recorded_start_at: AwareDatetime | None = None
    recorded_end_at: AwareDatetime | None = None
    size_bytes: int | None = Field(default=None, gt=0)
    config_snapshot: ConfigSnapshot | None = None
    # The worker's sealed manifest for this clip; the backend checks the file against it.
    source_manifest_ref: ManifestRef | None = None

    @model_validator(mode="after")
    def check_times(self) -> Self:
        if self.source_manifest_ref is not None and (
            self.size_bytes is None or self.recorded_start_at is None
        ):
            raise ValueError("A manifest needs size_bytes and the recorded start/end times.")
        # Each group is all-or-nothing: mixing sent values with a "now" fallback could
        # break the ordering the `events` and `video_clips` CHECKs enforce.
        event_times = [self.started_at, self.last_person_seen_at, self.closed_at]
        if any(t is not None for t in event_times):
            if any(t is None for t in event_times):
                raise ValueError(
                    "Send started_at, last_person_seen_at and closed_at together, or none."
                )
            if not self.started_at <= self.last_person_seen_at <= self.closed_at:
                raise ValueError("Expected started_at <= last_person_seen_at <= closed_at.")

        if (self.recorded_start_at is None) != (self.recorded_end_at is None):
            raise ValueError("Send recorded_start_at and recorded_end_at together, or neither.")
        if self.recorded_start_at is not None and self.recorded_end_at <= self.recorded_start_at:
            raise ValueError("recorded_end_at must be after recorded_start_at.")
        return self


class VideoClipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    part_number: int
    source_manifest_ref: str
    status: VideoStatus
    source_ready_at: datetime | None
    recorded_start_at: datetime | None
    recorded_end_at: datetime | None
    filepath: str | None
    size_bytes: int | None
    sha256: str | None
    failure_code: str | None
    expires_at: datetime
    delete_requested_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    camera_id: UUID
    event_type: EventType
    status: CaptureState
    started_at: datetime
    last_person_seen_at: datetime
    closed_at: datetime | None
    end_reason: str | None
    created_at: datetime
    config_snapshot: dict[str, JsonValue]
    clips: list[VideoClipResponse]
