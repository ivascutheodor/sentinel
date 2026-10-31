from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    FetchedValue,
    Index,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.camera_access import CameraAccess
    from app.db.models.event import Event


class Camera(Base):
    __tablename__ = "cameras"

    __table_args__ = (
        CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 200",
            name="name",
        ),
        CheckConstraint(
            """
            (stream_url ~ '^rtsp://[^/@[:space:]#?]+(/[^[:space:]#]*)?$') AND
            ((jsonb_typeof(detection_config) = 'object'
            AND detection_config ?& ARRAY['schema_version','region']
            AND detection_config->'schema_version' = '1'::jsonb
            AND (detection_config - 'schema_version' - 'region') = '{}'::jsonb
            AND (detection_config->'region' = 'null'::jsonb OR
             (jsonb_typeof(detection_config->'region') = 'object'
              AND (detection_config->'region') ?& ARRAY['type','points','match_rule']
              AND detection_config->'region'->>'type' = 'polygon'
              AND detection_config->'region'->>'match_rule' = 'bottom_center'
              AND ((detection_config->'region') - 'type' - 'points' - 'match_rule') =
            '{}'::jsonb
              AND CASE WHEN jsonb_typeof(detection_config->'region'->'points') = 'array'
                  THEN jsonb_array_length(detection_config->'region'->'points') BETWEEN 3
            AND 16
                  ELSE false END))) IS TRUE)
            """,
            name="stream_url",
        ),
        CheckConstraint(
            "credentials_ref IS NULL OR credentials_ref ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="credentials_ref",
        ),
        # The worker finds its camera by name, so "Entrance" and "entrance" must not both exist.
        Index("uq_cameras_name_lower", text("lower(name)"), unique=True),
        {
            "comment": (
                "Single-tenant camera identity survives changes of name, address and credentials. "
                "Exactly one recorder owns a camera at a time. Source/ROI changes while capturing "
                "require an audited stop/restart; do not silently change an open event. Set "
                "is_enabled=false to stop monitoring; this does not by itself revoke archival "
                "access."
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    stream_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    credentials_ref: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    detection_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
        server_default=text("jsonb_build_object('schema_version', 1, 'region', NULL)"),
    )

    last_frame_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_inference_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=FetchedValue(),
    )

    events: Mapped[list[Event]] = relationship(
        back_populates="camera",
        foreign_keys="Event.camera_id",
        passive_deletes="all",
    )

    access_grants: Mapped[list[CameraAccess]] = relationship(
        back_populates="camera",
        foreign_keys="CameraAccess.camera_id",
        passive_deletes="all",
    )
