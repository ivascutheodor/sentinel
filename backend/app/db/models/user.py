from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    FetchedValue,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import UserRole, user_role_type

if TYPE_CHECKING:
    from app.db.models.audit_log import AuditLog
    from app.db.models.camera_access import CameraAccess
    from app.db.models.user_session import UserSession


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "length(btrim(display_name)) BETWEEN 1 AND 200",
            name="display_name",
        ),
        CheckConstraint(
            "email = lower(btrim(email)) AND length(email) BETWEEN 3 AND 254",
            name="email",
        ),
        CheckConstraint(
            "length(btrim(password_hash)) > 0",
            name="password_hash",
        ),
        {
            "comment": (
                "Single-clinic accounts. Deactivate rather than hard-delete accounts referenced "
                "by historical records. Authentication must check is_active. A role change or "
                "deactivation also invalidates affected sessions/live authorizations."
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )

    display_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        user_role_type,
        nullable=False,
        server_default=text("'user'"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
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

    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="actor_user",
        foreign_keys="AuditLog.actor_user_id",
        passive_deletes="all",
    )

    camera_accesses: Mapped[list[CameraAccess]] = relationship(
        back_populates="user",
        foreign_keys="CameraAccess.user_id",
        passive_deletes="all",
    )

    grants_issued: Mapped[list[CameraAccess]] = relationship(
        back_populates="granted_by_user",
        foreign_keys="CameraAccess.granted_by",
        passive_deletes="all",
    )

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user",
        foreign_keys="UserSession.user_id",
        passive_deletes="all",
    )

    sessions_revoked: Mapped[list[UserSession]] = relationship(
        back_populates="revoked_by_user",
        foreign_keys="UserSession.revoked_by_user_id",
        passive_deletes="all",
    )
