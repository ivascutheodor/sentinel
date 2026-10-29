from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.models import User, UserSession


def revoke_sessions(
    session: Session, user_id: UUID, *, by: User, keep_session_id: UUID | None = None
) -> int:
    """Logs the user out everywhere (except `keep_session_id`); returns how many sessions.

    Used when a password, role or active flag changes: an open session must not keep the
    old rights until it expires.
    """
    now = datetime.now(UTC)
    statement = (
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        .values(revoked_at=now, revoked_by_user_id=by.id)
    )
    if keep_session_id is not None:
        statement = statement.where(UserSession.id != keep_session_id)
    return session.execute(statement).rowcount


def another_active_admin_exists(session: Session, user_id: UUID) -> bool:
    """True if an active admin other than `user_id` exists.

    `FOR UPDATE` locks the active admin rows until commit. If two admins demote each other
    at the same moment, the second request waits for the first, then sees its result and
    is refused, instead of both succeeding and leaving no admin.
    """
    admin_ids = session.scalars(
        select(User.id).where(User.role == UserRole.ADMIN, User.is_active).with_for_update()
    ).all()
    return any(admin_id != user_id for admin_id in admin_ids)
