from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import CaptureState, EventType, capture_state_type, event_type_type

if TYPE_CHECKING:
    from app.db.models.camera import Camera
    from app.db.models.video_clip import VideoClip


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        CheckConstraint(
            """
            (last_person_seen_at >= started_at
            AND (closed_at IS NULL OR closed_at >= last_person_seen_at)
            AND ((status = 'capturing' AND closed_at IS NULL AND end_reason IS NULL)
             OR (status = 'completed' AND closed_at IS NOT NULL AND end_reason IS NOT NULL
            AND end_reason = 'person_absent')
             OR (status = 'interrupted' AND closed_at IS NOT NULL AND end_reason IS NOT
            NULL
                 AND end_reason IN
            ('stream_lost','worker_restart','manual_stop','camera_disabled','inference_stalled','recording_failed'))))
            AND ((jsonb_typeof(config_snapshot) = 'object'
            AND config_snapshot ?&
            ARRAY['schema_version','model_ref','detection_config','settings']
            AND config_snapshot->'schema_version' = '1'::jsonb
            AND jsonb_typeof(config_snapshot->'model_ref') = 'string'
            AND length(btrim(config_snapshot->>'model_ref')) > 0
            AND jsonb_typeof(config_snapshot->'detection_config') = 'object'
            AND jsonb_typeof(config_snapshot->'settings') = 'object') IS TRUE)
            """,
            name="end_reason",
        ),
        Index("ix_events_camera_id_started_at", "camera_id", "started_at", unique=False),
        Index("ix_events_started_at", "started_at", unique=False),
        Index(
            "uq_events_one_capturing_per_camera",
            "camera_id",
            unique=True,
            postgresql_where=text("status = 'capturing'"),
        ),
        {
            "comment": (
                "One continuous presence interval per camera, including overlapping people. "
                "Required partial unique index limits capturing events to one per camera "
                "(implemented in companion SQL). Snapshot settings at start; terminal event does "
                "not imply all clips are ready. Keep event metadata after video retention."
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    camera_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "cameras.id",
            name="fk_events_camera_id_cameras",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
    )

    event_type: Mapped[EventType] = mapped_column(
        event_type_type,
        nullable=False,
        server_default=text("'person_presence'"),
    )

    status: Mapped[CaptureState] = mapped_column(
        capture_state_type,
        nullable=False,
        server_default=text("'capturing'"),
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_person_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    end_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    config_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
    )

    camera: Mapped[Camera] = relationship(
        back_populates="events",
        foreign_keys=[camera_id],
    )

    clips: Mapped[list[VideoClip]] = relationship(
        back_populates="event",
        foreign_keys="VideoClip.event_id",
        passive_deletes="all",
    )

    @property
    def camera_name(self) -> str:
        """For API responses; load `Event.camera` with the query to avoid one query per event."""
        return self.camera.name
