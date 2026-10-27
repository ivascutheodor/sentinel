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
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    model_ref: NonBlank
    detection_config: dict[str, JsonValue]
    settings: dict[str, JsonValue]


class VideoClipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_number: int = Field(ge=1)
    source_manifest_ref: NonBlank
    expires_at: AwareDatetime
    status: Literal[VideoStatus.PENDING, VideoStatus.READY] = VideoStatus.PENDING
    source_ready_at: AwareDatetime | None = None
    recorded_start_at: AwareDatetime | None = None
    recorded_end_at: AwareDatetime | None = None
    filepath: NonBlank | None = None
    size_bytes: int | None = Field(default=None, gt=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_recording(self) -> Self:
        start, end = self.recorded_start_at, self.recorded_end_at
        if (start is None) != (end is None):
            raise ValueError("recorded_start_at and recorded_end_at must be supplied together")
        if start is not None and end is not None and end <= start:
            raise ValueError("recorded_end_at must be after recorded_start_at")
        if self.status == VideoStatus.READY and any(
            value is None
            for value in (self.filepath, self.size_bytes, start, end, self.source_ready_at)
        ):
            raise ValueError(
                "Ready clips require filepath, size_bytes, recording times and source_ready_at"
            )
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


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_id: UUID
    event_type: EventType = EventType.PERSON_PRESENCE
    status: CaptureState = CaptureState.CAPTURING
    started_at: AwareDatetime
    last_person_seen_at: AwareDatetime
    closed_at: AwareDatetime | None = None
    end_reason: EndReason | None = None
    config_snapshot: ConfigSnapshot
    clips: list[VideoClipCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_capture(self) -> Self:
        if self.last_person_seen_at < self.started_at:
            raise ValueError("last_person_seen_at must be at or after started_at")
        if self.closed_at is not None and self.closed_at < self.last_person_seen_at:
            raise ValueError("closed_at must be at or after last_person_seen_at")
        if self.status == CaptureState.CAPTURING:
            if self.closed_at is not None or self.end_reason is not None:
                raise ValueError("Capturing events cannot have closed_at or end_reason")
        else:
            if self.closed_at is None or self.end_reason is None:
                raise ValueError("Closed events require closed_at and end_reason")
            if self.status == CaptureState.COMPLETED and self.end_reason != "person_absent":
                raise ValueError("Completed events require end_reason='person_absent'")
            if self.status == CaptureState.INTERRUPTED and self.end_reason == "person_absent":
                raise ValueError("Interrupted events require an interruption reason")
        if len({clip.part_number for clip in self.clips}) != len(self.clips):
            raise ValueError("Clip part numbers must be unique within an event")
        return self


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
