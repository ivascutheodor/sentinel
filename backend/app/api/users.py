"""User management for admins. Accounts are deactivated, never deleted: audit rows point to them."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminDep, SessionDep
from app.core.security import hash_password
from app.db.enums import AuditOutcome, UserRole
from app.db.models import User
from app.schemas.users import PasswordReset, UserAdminResponse, UserCreate, UserUpdate
from app.services.audit import audit
from app.services.users import another_active_admin_exists, revoke_sessions

router = APIRouter(prefix="/users", tags=["Users"])


def user_or_404(session: SessionDep, user_id: UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("", response_model=list[UserAdminResponse])
def list_users(session: SessionDep, admin: AdminDep) -> list[User]:
    return list(session.scalars(select(User).order_by(User.username)).all())


@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, session: SessionDep, admin: AdminDep) -> User:
    user = User(
        username=body.username,
        display_name=body.display_name,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:  # `users.username` is unique
        session.rollback()
        raise conflict(f"A user named {body.username!r} already exists.") from exc
    audit(
        session,
        "user.create",
        AuditOutcome.SUCCESS,
        user=admin,
        resource=("user", str(user.id)),
        details={"role": user.role.value},
    )
    session.commit()
    return user


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(user_id: UUID, body: UserUpdate, session: SessionDep, admin: AdminDep) -> User:
    user = user_or_404(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return user

    new_role = changes.get("role", user.role)
    new_active = changes.get("is_active", user.is_active)
    loses_admin = (
        user.role == UserRole.ADMIN
        and user.is_active
        and (new_role != UserRole.ADMIN or not new_active)
    )
    if loses_admin:
        # Checked here, not in the frontend: the system must never be left without an admin.
        if user.id == admin.id:
            raise conflict("You cannot remove your own administrator access.")
        if not another_active_admin_exists(session, user.id):
            raise conflict("At least one active administrator must remain.")

    role_changed = new_role != user.role
    deactivated = user.is_active and not new_active
    for field, value in changes.items():
        setattr(user, field, value)
    user.updated_at = datetime.now(UTC)
    # As the `users` table comment requires: open sessions must not keep the old rights.
    revoked = revoke_sessions(session, user.id, by=admin) if role_changed or deactivated else 0

    details: dict = {"fields": sorted(changes), "sessions_revoked": revoked}
    if "role" in changes:
        details["role"] = new_role.value
    if "is_active" in changes:
        details["is_active"] = new_active
    audit(
        session,
        "user.update",
        AuditOutcome.SUCCESS,
        user=admin,
        resource=("user", str(user.id)),
        details=details,
    )
    session.commit()
    return user


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: UUID, body: PasswordReset, session: SessionDep, admin: AdminDep
) -> None:
    user = user_or_404(session, user_id)
    if user.id == admin.id:
        # Changing your own password needs the current one: /auth/password.
        raise conflict("Use /auth/password to change your own password.")
    user.password_hash = hash_password(body.new_password)
    user.updated_at = datetime.now(UTC)
    revoked = revoke_sessions(session, user.id, by=admin)
    audit(
        session,
        "user.password_reset",
        AuditOutcome.SUCCESS,
        user=admin,
        resource=("user", str(user.id)),
        details={"sessions_revoked": revoked},
    )
    session.commit()
