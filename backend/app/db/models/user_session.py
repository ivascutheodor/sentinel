from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, Text, Uuid, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class UserSession(Base):
    __tablename__ = "user_sessions"

    __table_args__ = (
        CheckConstraint(
            """
            octet_length(token_hash) = 32
            AND last_seen_at >= created_at
            AND expires_at > created_at
            AND (revoked_at IS NULL OR revoked_at >= created_at)
            AND (revoked_by_user_id IS NULL OR revoked_at IS NOT NULL)
            """,
            name="user_agent",
        ),
        Index("ix_user_sessions_user_id_created_at", "user_id", "created_at", unique=False),
        Index("ix_user_sessions_expires_at", "expires_at", unique=False),
        {
            "comment": (
                "One row per authenticated browser session. Backend checks token hash, user "
                "activity, revocation, absolute expiry and idle timeout for every protected "
                "operation. Revocation must propagate to active video and WebSocket connections. "
                "User-agent is descriptive, not a physical-device identifier."
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_user_sessions_user_id_users",
            ondelete="CASCADE",
            onupdate="NO ACTION",
        ),
        nullable=False,
    )

    token_hash: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_user_sessions_revoked_by_user_id_users",
            ondelete="SET NULL",
            onupdate="NO ACTION",
        ),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_ip: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="sessions",
        foreign_keys=[user_id],
    )

    revoked_by_user: Mapped[User | None] = relationship(
        back_populates="sessions_revoked",
        foreign_keys=[revoked_by_user_id],
    )
