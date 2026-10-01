from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import VideoStatus, video_status_type

if TYPE_CHECKING:
    from app.db.models.event import Event
    from app.db.models.media_job import MediaJob


class VideoClip(Base):
    __tablename__ = "video_clips"

    __table_args__ = (
        CheckConstraint(
            "part_number >= 1",
            name="part_number",
        ),
        CheckConstraint(
            "length(btrim(source_manifest_ref)) > 0",
            name="source_manifest_ref",
        ),
        CheckConstraint(
            """
            (
                (filepath IS NULL OR length(btrim(filepath)) > 0)
                AND (
                    status <> 'ready' OR
                    (filepath IS NOT NULL AND
                    size_bytes IS NOT NULL AND
                    size_bytes > 0 AND
                    recorded_start_at IS NOT NULL AND
                    recorded_end_at IS NOT NULL AND
                    source_ready_at IS NOT NULL))
                    )
                AND (
                    (recorded_start_at IS NULL AND
                    recorded_end_at IS NULL)
                OR (
                    recorded_start_at IS NOT NULL AND
                    recorded_end_at IS NOT NULL AND
                    recorded_end_at > recorded_start_at))
                AND ((status IN ('deleting','deleted') AND
                    delete_requested_at IS NOT NULL)
                OR (status NOT IN ('deleting','deleted') AND
                    delete_requested_at IS NULL)) AND
                    ((status = 'deleted' AND
                    deleted_at IS NOT NULL AND
                    deleted_at >= delete_requested_at) OR
                    (status <> 'deleted' AND deleted_at IS NULL)
            )
            """,
            name="filepath",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0",
            name="size_bytes",
        ),
        CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="sha256",
        ),
        CheckConstraint(
            """
            (failure_code IS NULL OR length(btrim(failure_code)) > 0)
            AND (status <> 'failed' OR failure_code IS NOT NULL)
            AND (status NOT IN ('pending','ready') OR failure_code IS NULL)
            """,
            name="failure_code",
        ),
        UniqueConstraint("event_id", "part_number", name="uq_video_clips_event_part"),
        Index("ix_video_clips_status_expires_at", "status", "expires_at", unique=False),
        {
            "comment": (
                "Clip lifecycle: pending -> ready/failed/deleting; failed -> pending (explicit "
                "retry) or deleting; ready -> failed (verified missing/corrupt file) or deleting; "
                "deleting -> deleted; deleted is terminal. Required SQL triggers enforce "
                "transitions. A source manifest identifies recoverable input even while pending. "
                "Finalization and deletion are serialized using clip row locking plus valid job "
                "token; database transactions never include the full video processing duration."
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "events.id",
            name="fk_video_clips_event_id_events",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
    )

    part_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_manifest_ref: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    source_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    recorded_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    recorded_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    filepath: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    sha256: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[VideoStatus] = mapped_column(
        video_status_type,
        nullable=False,
        server_default=text("'pending'"),
    )

    failure_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    delete_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    event: Mapped[Event] = relationship(
        back_populates="clips",
        foreign_keys=[event_id],
    )

    jobs: Mapped[list[MediaJob]] = relationship(
        back_populates="clip",
        foreign_keys="MediaJob.clip_id",
        passive_deletes="all",
    )
