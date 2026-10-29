from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    StringConstraints,
    model_validator,
)

# Each rule mirrors a CHECK on `cameras`, so a mistake is a 422 with a message, not a 500.
CameraName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# The DB pattern, with `[:space:]` written as `\s`. No `@`, so no password inside the URL.
StreamUrl = Annotated[str, StringConstraints(pattern=r"^rtsp://[^/@\s#?]+(/[^\s#]*)?$")]
CredentialsRef = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class Region(BaseModel):
    """The restricted zone: a polygon in pixels; a person counts when their foot point is in it."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["polygon"] = "polygon"
    points: list[tuple[NonNegativeInt, NonNegativeInt]] = Field(min_length=3, max_length=16)
    match_rule: Literal["bottom_center"] = "bottom_center"


class DetectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    region: Region | None = None


class CameraSummary(BaseModel):
    """What every logged-in user sees: enough to name and filter, nothing about the network."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    location: str | None
    is_enabled: bool
    last_frame_at: datetime | None


class CameraDetail(CameraSummary):
    """Admins only: includes where the stream lives."""

    stream_url: str
    credentials_ref: str | None
    detection_config: DetectionConfig
    last_inference_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CameraName  # what the worker sends as `camera_id`
    location: Location | None = None
    stream_url: StreamUrl
    credentials_ref: CredentialsRef | None = None
    is_enabled: bool = False
    detection_config: DetectionConfig = DetectionConfig()


class CameraUpdate(BaseModel):
    """Only the fields sent are changed. `location` and `credentials_ref` may be null."""

    model_config = ConfigDict(extra="forbid")

    name: CameraName | None = None
    location: Location | None = None
    stream_url: StreamUrl | None = None
    credentials_ref: CredentialsRef | None = None
    is_enabled: bool | None = None
    detection_config: DetectionConfig | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for field in ("name", "stream_url", "is_enabled", "detection_config"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self
