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
from app.db.enums import AuditOutcome, audit_outcome_type

if TYPE_CHECKING:
    from app.db.models.user import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        CheckConstraint(
            """
            (actor_type = 'user' AND actor_user_id IS NOT NULL AND actor_service IS NULL)
            OR (actor_type = 'system' AND actor_user_id IS NULL AND actor_service IS NOT
            NULL AND length(btrim(actor_service)) > 0)
            OR (actor_type = 'anonymous' AND actor_user_id IS NULL AND actor_service IS
            NULL)
            """,
            name="actor_type",
        ),
        CheckConstraint(
            """
            (length(btrim(action)) > 0) AND (details IS NULL OR jsonb_typeof(details) =
            'object')
            """,
            name="action",
        ),
        CheckConstraint(
            """
            (resource_type IS NULL AND resource_id IS NULL)
            OR (resource_type IS NOT NULL AND resource_id IS NOT NULL AND
            length(btrim(resource_type)) > 0 AND length(btrim(resource_id)) > 0)
            """,
            name="resource_id",
        ),
        Index("ix_audit_logs_occurred_at", "occurred_at", unique=False),
        Index(
            "ix_audit_logs_actor_user_id_occurred_at",
            "actor_user_id",
            "occurred_at",
            unique=False,
        ),
        Index(
            "ix_audit_logs_resource_type_resource_id_occurred_at",
            "resource_type",
            "resource_id",
            "occurred_at",
            unique=False,
        ),
        {
            "comment": """
            Append-only application history; companion SQL rejects UPDATE/DELETE/TRUNCATE.
            Runtime role must not own tables or disable triggers.
            Retention/export is a separately authorized owner maintenance procedure.
            User FKs use NO ACTION and users are normally deactivated.
            Audit and event-metadata retention are separate from video retention."
            """
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    actor_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_audit_logs_actor_user_id_users",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=True,
    )

    actor_service: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    resource_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    outcome: Mapped[AuditOutcome] = mapped_column(
        audit_outcome_type,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    request_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )

    actor_user: Mapped[User | None] = relationship(
        back_populates="audit_logs",
        foreign_keys=[actor_user_id],
    )
