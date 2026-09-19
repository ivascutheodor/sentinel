from enum import StrEnum

from sqlalchemy import Enum as SQLAlchemyEnum


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"

class CaptureState(StrEnum):
    CAPTURING = "capturing"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"

class VideoStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"

class MediaStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EventType(StrEnum):
    PERSON_PRESENCE = "person_presence"

class AuditOutcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"

user_role_type = SQLAlchemyEnum(
    UserRole,
    name="roles",
    values_callable=_enum_values,
    validate_strings=True,
    native_enum=True,
)

capture_state_type = SQLAlchemyEnum(
    CaptureState,
    name="capture_states",
    values_callable=_enum_values,
    validate_strings=True,
    native_enum=True,
)

video_status_type = SQLAlchemyEnum(
    VideoStatus,
    name="video_status",
    values_callable=_enum_values,
    validate_strings=True,
    native_enum=True,
)

media_status_type = SQLAlchemyEnum(
    MediaStatus,
    name="media_status",
    values_callable=_enum_values,
    validate_strings=True,
    native_enum=True,
)

event_type_type = SQLAlchemyEnum(
    EventType,
    name="event_types",
    values_callable=_enum_values,
    validate_strings=True,
    native_enum=True,
)

audit_outcome_type = SQLAlchemyEnum(
    AuditOutcome,
    name="audit_outcomes",
    values_callable=_enum_values,
    validate_strings=True,
    native_enum=True,
)
