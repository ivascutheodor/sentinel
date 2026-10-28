from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from app.api.deps import (
    CurrentSessionDep,
    CurrentUserDep,
    SessionDep,
    client_ip,
    unauthorized,
)
from app.core.config import get_settings
from app.core.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)
from app.db.enums import AuditOutcome
from app.db.models import User, UserSession
from app.schemas.auth import LoginRequest, UserResponse
from app.services.audit import audit
from app.services.system_settings import get_system_settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=UserResponse)
def login(
    credentials: LoginRequest, request: Request, response: Response, session: SessionDep
) -> User:
    settings = get_settings()
    username = credentials.username.strip().lower()
    user = session.scalar(select(User).where(User.username == username))

    if user is None:
        verify_dummy_password(credentials.password)
        valid = False
    else:
        valid = verify_password(user.password_hash, credentials.password) and user.is_active

    if user is None or not valid:
        audit(
            session,
            "session.login",
            AuditOutcome.DENIED,
            resource=("user", str(user.id)) if user is not None else None,
        )
        session.commit()
        raise unauthorized("Invalid username or password.")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(credentials.password)

    lifetime_seconds = get_system_settings(session).session_absolute_seconds
    now = datetime.now(UTC)
    token = new_session_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=lifetime_seconds),
            user_agent=request.headers.get("user-agent"),
            last_ip=client_ip(request),
        )
    )
    audit(session, "session.login", AuditOutcome.SUCCESS, user=user)
    session.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=lifetime_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user_session: CurrentSessionDep, response: Response, session: SessionDep) -> None:
    settings = get_settings()
    user_session.revoked_at = datetime.now(UTC)
    user_session.revoked_by_user_id = user_session.user_id
    audit(session, "session.logout", AuditOutcome.SUCCESS, user=user_session.user)
    session.commit()

    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUserDep) -> User:
    return user
