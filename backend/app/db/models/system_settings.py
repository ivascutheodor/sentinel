from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    FetchedValue,
    Integer,
    SmallInteger,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    __table_args__ = (
        CheckConstraint(
            "id = 1",
            name="id",
        ),
        CheckConstraint(
            "retention_days > 0",
            name="retention_days",
        ),
        CheckConstraint(
            "pre_roll_seconds >= 0",
            name="pre_roll_seconds",
        ),
        CheckConstraint(
            "post_roll_seconds >= 0",
            name="post_roll_seconds",
        ),
        CheckConstraint(
            "clip_part_seconds > 0",
            name="clip_part_seconds",
        ),
        CheckConstraint(
            "confidence_threshold >= 0 AND confidence_threshold <= 1",
            name="confidence_threshold",
        ),
        CheckConstraint(
            "session_absolute_seconds > 0",
            name="session_absolute_seconds",
        ),
        CheckConstraint(
            """
            session_idle_seconds > 0 AND session_idle_seconds <= session_absolute_seconds
            """,
            name="session_idle_seconds",
        ),
        {
            "comment": (
                "Singleton per installation, not per camera. Seed values are initial engineering "
                "defaults: retention 7 days, pre/post 10 seconds, parts 60 seconds, confidence "
                "0.60; Updates affect newly created events. Existing events use config_snapshot; "
                "existing clip expiries are not silently rewritten. Controlled retention changes "
                "on existing data require a separate audited operation."
            )
        },
    )

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        autoincrement=False,
        nullable=False,
        server_default=text("1"),
    )

    retention_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("7"),
    )

    pre_roll_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("10"),
    )

    post_roll_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("10"),
    )

    clip_part_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("60"),
    )

    confidence_threshold: Mapped[float] = mapped_column(
        DOUBLE_PRECISION,
        nullable=False,
        server_default=text("0.60"),
    )

    session_absolute_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("43200"),
    )

    session_idle_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1800"),
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
