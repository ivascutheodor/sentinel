"""Dependencies shared by the routers: database session, current user, worker key."""

import ipaddress
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import hash_session_token
from app.db.models import User, UserSession
from app.db.session import get_session
from app.services.system_settings import get_system_settings

# `last_seen_at` is written at most this often, so video range requests don't
# turn every chunk into a database write.
SESSION_TOUCH_INTERVAL = timedelta(seconds=60)

SessionDep = Annotated[Session, Depends(get_session)]


def unauthorized(detail: str = "Not authenticated.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def client_ip(request: Request) -> str | None:
    """`user_sessions.last_ip` is INET, so anything that isn't an IP is dropped."""
    if request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None


def get_current_session(request: Request, session: SessionDep) -> UserSession:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token is None:
        raise unauthorized()

    user_session = session.scalar(
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.token_hash == hash_session_token(token))
    )
    if user_session is None:
        raise unauthorized()

    # The absolute deadline was fixed at login (`expires_at`); the idle timeout is read
    # now, so changing it in `system_settings` also applies to sessions already open.
    idle_timeout = timedelta(seconds=get_system_settings(session).session_idle_seconds)
    now = datetime.now(UTC)
    if (
        user_session.revoked_at is not None
        or user_session.expires_at <= now
        or user_session.last_seen_at + idle_timeout <= now
        or not user_session.user.is_active
    ):
        raise unauthorized()

    if now - user_session.last_seen_at >= SESSION_TOUCH_INTERVAL:
        user_session.last_seen_at = now
        user_session.last_ip = client_ip(request)
        session.commit()
    return user_session


CurrentSessionDep = Annotated[UserSession, Depends(get_current_session)]


def get_current_user(user_session: CurrentSessionDep) -> User:
    return user_session.user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def verify_worker_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().worker_api_key.get_secret_value().encode()
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), expected):
        raise unauthorized("Invalid worker API key.")
