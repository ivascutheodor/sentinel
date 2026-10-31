from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Upper bounds keep values inside a PostgreSQL INTEGER, and `retention_days` inside what a
# date can hold (a clip's `expires_at = now + retention`).
Seconds = Annotated[int, Field(ge=1, le=2_147_483_647)]
RollSeconds = Annotated[int, Field(ge=0, le=2_147_483_647)]
RetentionDays = Annotated[int, Field(ge=1, le=3650)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class SystemSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retention_days: int
    pre_roll_seconds: int
    post_roll_seconds: int
    clip_part_seconds: int
    confidence_threshold: float
    session_absolute_seconds: int
    session_idle_seconds: int
    updated_at: datetime


class SystemSettingsUpdate(BaseModel):
    """Only the fields sent are changed; none of them may be null.

    The rule "idle <= absolute" is checked by the route after merging with the stored row,
    because a request may send only one of the two.
    """

    model_config = ConfigDict(extra="forbid")

    retention_days: RetentionDays | None = None
    pre_roll_seconds: RollSeconds | None = None
    post_roll_seconds: RollSeconds | None = None
    clip_part_seconds: Seconds | None = None
    confidence_threshold: Confidence | None = None
    session_absolute_seconds: Seconds | None = None
    session_idle_seconds: Seconds | None = None

    @model_validator(mode="after")
    def no_nulls(self) -> Self:
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Fields cannot be set to null; leave them out instead.")
        return self
