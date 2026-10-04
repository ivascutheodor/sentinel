from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.camera import Camera
    from app.db.models.user import User


class CameraAccess(Base):
    __tablename__ = "camera_access"

    __table_args__ = (
        Index("ix_camera_access_camera_id_user_id", "camera_id", "user_id", unique=False),
        {
            "comment": """
            Composite PRIMARY KEY(user_id,camera_id).
            Both parent relationships are many-to-one.
            Active admins access all cameras; active users access only assigned cameras
            and their events/clips.
            Grant/revoke is authorized and audited by backend.
            Revoking access terminates affected active streams.
            """
        },
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_camera_access_user_id_users",
            ondelete="CASCADE",
            onupdate="NO ACTION",
        ),
        primary_key=True,
        nullable=False,
    )

    camera_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "cameras.id",
            name="fk_camera_access_camera_id_cameras",
            ondelete="CASCADE",
            onupdate="NO ACTION",
        ),
        primary_key=True,
        nullable=False,
    )

    granted_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_camera_access_granted_by_users",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
    )

    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped[User] = relationship(
        back_populates="camera_accesses",
        foreign_keys=[user_id],
    )

    camera: Mapped[Camera] = relationship(
        back_populates="access_grants",
        foreign_keys=[camera_id],
    )

    granted_by_user: Mapped[User] = relationship(
        back_populates="grants_issued",
        foreign_keys=[granted_by],
    )
