from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
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
from app.db.enums import MediaStatus, media_status_type

if TYPE_CHECKING:
    from app.db.models.video_clip import VideoClip


class MediaJob(Base):
    __tablename__ = "media_jobs"

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('finalize_clip','delete_clip')",
            name="job_type",
        ),
        CheckConstraint(
            """
            attempt_count >= 0 AND attempt_count <= max_attempts
            AND (status NOT IN ('running','succeeded') OR attempt_count >= 1)
            AND ((status = 'running' AND lock_token IS NOT NULL AND locked_until IS NOT
            NULL)
             OR (status <> 'running' AND lock_token IS NULL AND locked_until IS NULL))
            AND (status <> 'failed' OR last_error_code IS NOT NULL)
            """,
            name="attempt_count",
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="max_attempts",
        ),
        CheckConstraint(
            "last_error_code IS NULL OR length(btrim(last_error_code)) > 0",
            name="last_error_code",
        ),
        UniqueConstraint("clip_id", "job_type", name="uq_media_jobs_clip_type"),
        Index(
            "ix_media_jobs_status_available_at_created_at",
            "status",
            "available_at",
            "created_at",
            unique=False,
        ),
        Index("ix_media_jobs_status_locked_until", "status", "locked_until", unique=False),
        Index(
            "uq_media_jobs_one_running_per_clip",
            "clip_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        {
            "comment": (
                "At-least-once work queue, not exactly-once external side effects. "
                "UNIQUE(clip_id,job_type) prevents duplicate logical jobs. Required partial "
                "unique index allows at most one running job per clip across all types. "
                "Lease/token checks, deterministic manifests, immutable attempt outputs and "
                "reconciliation provide safe retries. Acquire clip then job locks in consistent "
                "order; see worker protocol note."
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    clip_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "video_clips.id",
            name="fk_media_jobs_clip_id_video_clips",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
    )

    job_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[MediaStatus] = mapped_column(
        media_status_type,
        nullable=False,
        server_default=text("'queued'"),
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("5"),
    )

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    lock_token: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
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

    clip: Mapped[VideoClip] = relationship(
        back_populates="jobs",
        foreign_keys=[clip_id],
    )
