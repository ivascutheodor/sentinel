from __future__ import annotations

import ipaddress
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

# Make the sibling `app` package importable no matter where this file is launched from.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.security import (  # noqa: E402
    hash_password,
    hash_session_token,
    new_session_token,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)
from app.core.version import get_version  # noqa: E402
from app.db.enums import (  # noqa: E402
    AuditOutcome,
    CaptureState,
    EventType,
    UserRole,
    VideoStatus,
)
from app.db.models import AuditLog, Camera, Event, User, UserSession, VideoClip  # noqa: E402
from app.db.session import get_session  # noqa: E402

settings = get_settings()

SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(title=settings.app_name, version=get_version(), debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Range"],
)

PROJECT_ROOT = BACKEND_DIR.parent
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RETENTION_DAYS = 7
DEFAULT_MODEL_REF = "yolo11n.pt"

# Same values as the `system_settings` column defaults; read them from that row
# once it is seeded.
DEFAULT_SESSION_ABSOLUTE_SECONDS = 43200
DEFAULT_SESSION_IDLE_SECONDS = 1800

# `last_seen_at` is written at most this often, so video range requests don't
# turn every chunk into a database write.
SESSION_TOUCH_INTERVAL = timedelta(seconds=60)

# Minimal but valid `events.config_snapshot` payload. The JSONB CHECK on the
# `events` table requires `schema_version`, `model_ref`, `detection_config` and
# `settings`; replace this with a real snapshot as soon as the worker sends one.
DEFAULT_CONFIG_SNAPSHOT: dict = {
    "schema_version": 1,
    "model_ref": DEFAULT_MODEL_REF,
    "detection_config": {"schema_version": 1, "region": None},
    "settings": {},
}


# Values allowed by the `events` CHECK; anything but `person_absent` means `interrupted`.
EndReason = Literal[
    "person_absent",
    "stream_lost",
    "worker_restart",
    "manual_stop",
    "camera_disabled",
    "inference_stalled",
    "recording_failed",
]


class ConfigSnapshot(BaseModel):
    """Mirrors the `events.config_snapshot` CHECK, so a bad snapshot is a 422, not a 500."""

    schema_version: Literal[1] = 1
    model_ref: str = Field(min_length=1)
    detection_config: dict[str, Any]
    settings: dict[str, Any]


class EventCreate(BaseModel):
    camera_id: str
    video_path: str

    # Optional so a worker that only sends the two fields above still works; the
    # backend then falls back to "now" and leaves the clip `pending`.
    started_at: AwareDatetime | None = None
    last_person_seen_at: AwareDatetime | None = None
    closed_at: AwareDatetime | None = None
    end_reason: EndReason = "person_absent"
    recorded_start_at: AwareDatetime | None = None
    recorded_end_at: AwareDatetime | None = None
    size_bytes: int | None = Field(default=None, gt=0)
    config_snapshot: ConfigSnapshot | None = None

    @model_validator(mode="after")
    def check_times(self) -> EventCreate:
        # Each group is all-or-nothing: mixing sent values with a "now" fallback could
        # break the ordering the `events` and `video_clips` CHECKs enforce.
        event_times = [self.started_at, self.last_person_seen_at, self.closed_at]
        if any(t is not None for t in event_times):
            if any(t is None for t in event_times):
                raise ValueError(
                    "Send started_at, last_person_seen_at and closed_at together, or none."
                )
            if not self.started_at <= self.last_person_seen_at <= self.closed_at:
                raise ValueError("Expected started_at <= last_person_seen_at <= closed_at.")

        if (self.recorded_start_at is None) != (self.recorded_end_at is None):
            raise ValueError("Send recorded_start_at and recorded_end_at together, or neither.")
        if self.recorded_start_at is not None and self.recorded_end_at <= self.recorded_start_at:
            raise ValueError("recorded_end_at must be after recorded_start_at.")
        return self


class EventResponse(BaseModel):
    id: UUID
    camera_id: UUID
    video_path: str | None
    created_at: datetime
    status: CaptureState
    started_at: datetime
    last_person_seen_at: datetime
    closed_at: datetime | None
    duration_seconds: float | None
    clip_status: VideoStatus | None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole


def _to_response(event: Event) -> EventResponse:
    clip = event.clips[0] if event.clips else None
    duration = (event.closed_at - event.started_at).total_seconds() if event.closed_at else None
    return EventResponse(
        id=event.id,
        camera_id=event.camera_id,
        video_path=clip.filepath if clip else None,
        created_at=event.created_at,
        status=event.status,
        started_at=event.started_at,
        last_person_seen_at=event.last_person_seen_at,
        closed_at=event.closed_at,
        duration_seconds=duration,
        clip_status=clip.status if clip else None,
    )


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


def _resolve_camera(session: Session, camera_id: str) -> Camera:
    camera = session.scalar(select(Camera).where(Camera.name == camera_id))
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id!r} not found.",
        )
    return camera


def _client_ip(request: Request) -> str | None:
    """`user_sessions.last_ip` is INET, so anything that isn't an IP is dropped."""
    if request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None


def _audit(
    session: Session,
    action: str,
    outcome: AuditOutcome,
    *,
    user: User | None = None,
    service: str | None = None,
    resource: tuple[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    if user is not None:
        actor_type = "user"
    elif service is not None:
        actor_type = "system"
    else:
        actor_type = "anonymous"
    resource_type, resource_id = resource if resource is not None else (None, None)
    session.add(
        AuditLog(
            actor_type=actor_type,
            actor_user_id=user.id if user is not None else None,
            actor_service=service,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            details=details,
        )
    )


def _unauthorized(detail: str = "Not authenticated.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_session(request: Request, session: SessionDep) -> UserSession:
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise _unauthorized()

    user_session = session.scalar(
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.token_hash == hash_session_token(token))
    )
    now = datetime.now(UTC)
    if (
        user_session is None
        or user_session.revoked_at is not None
        or user_session.expires_at <= now
        or user_session.last_seen_at + timedelta(seconds=DEFAULT_SESSION_IDLE_SECONDS) <= now
        or not user_session.user.is_active
    ):
        raise _unauthorized()

    if now - user_session.last_seen_at >= SESSION_TOUCH_INTERVAL:
        user_session.last_seen_at = now
        user_session.last_ip = _client_ip(request)
        session.commit()
    return user_session


CurrentSessionDep = Annotated[UserSession, Depends(get_current_session)]


def get_current_user(user_session: CurrentSessionDep) -> User:
    return user_session.user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def verify_worker_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = settings.worker_api_key.get_secret_value().encode()
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), expected):
        raise _unauthorized("Invalid worker API key.")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }


@app.post("/api/v1/auth/login", response_model=UserResponse, tags=["Auth"])
def login(credentials: LoginRequest, request: Request, response: Response, session: SessionDep):
    username = credentials.username.strip().lower()
    user = session.scalar(select(User).where(User.username == username))

    if user is None:
        verify_dummy_password(credentials.password)
        valid = False
    else:
        valid = verify_password(user.password_hash, credentials.password) and user.is_active

    if user is None or not valid:
        _audit(
            session,
            "session.login",
            AuditOutcome.DENIED,
            resource=("user", str(user.id)) if user is not None else None,
        )
        session.commit()
        raise _unauthorized("Invalid username or password.")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(credentials.password)

    now = datetime.now(UTC)
    token = new_session_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=DEFAULT_SESSION_ABSOLUTE_SECONDS),
            user_agent=request.headers.get("user-agent"),
            last_ip=_client_ip(request),
        )
    )
    _audit(session, "session.login", AuditOutcome.SUCCESS, user=user)
    session.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=DEFAULT_SESSION_ABSOLUTE_SECONDS,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return _to_user_response(user)


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Auth"])
def logout(user_session: CurrentSessionDep, response: Response, session: SessionDep):
    user_session.revoked_at = datetime.now(UTC)
    user_session.revoked_by_user_id = user_session.user_id
    _audit(session, "session.logout", AuditOutcome.SUCCESS, user=user_session.user)
    session.commit()

    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return None


@app.get("/api/v1/auth/me", response_model=UserResponse, tags=["Auth"])
def me(user: CurrentUserDep):
    return _to_user_response(user)


@app.post(
    "/api/v1/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Events"],
    summary="Saves a new indexed video",
    dependencies=[Depends(verify_worker_key)],
)
def create_event_db(event: EventCreate, session: SessionDep):
    camera = _resolve_camera(session, event.camera_id)

    now = datetime.now(UTC)
    new_event = Event(
        camera_id=camera.id,
        event_type=EventType.PERSON_PRESENCE,
        status=(
            CaptureState.COMPLETED
            if event.end_reason == "person_absent"
            else CaptureState.INTERRUPTED
        ),
        started_at=event.started_at or now,
        last_person_seen_at=event.last_person_seen_at or now,
        closed_at=event.closed_at or now,
        end_reason=event.end_reason,
        config_snapshot=(
            event.config_snapshot.model_dump() if event.config_snapshot else DEFAULT_CONFIG_SNAPSHOT
        ),
    )
    session.add(new_event)
    session.flush()  # populate new_event.id before linking the clip

    # The `video_clips` CHECK only allows `ready` once the file's size and time span are known.
    is_ready = event.size_bytes is not None and event.recorded_start_at is not None
    clip = VideoClip(
        event_id=new_event.id,
        part_number=1,
        source_manifest_ref=f"manifests/{uuid4()}.json",
        filepath=event.video_path,
        status=VideoStatus.READY if is_ready else VideoStatus.PENDING,
        size_bytes=event.size_bytes,
        recorded_start_at=event.recorded_start_at,
        recorded_end_at=event.recorded_end_at,
        source_ready_at=now if is_ready else None,
        expires_at=now + timedelta(days=DEFAULT_RETENTION_DAYS),
    )
    session.add(clip)
    session.commit()
    session.refresh(new_event)

    return _to_response(new_event)


@app.get(
    "/api/v1/events",
    response_model=list[EventResponse],
    dependencies=[Depends(get_current_user)],
)
def get_all_events(session: SessionDep):
    events = session.scalars(select(Event).options(selectinload(Event.clips))).all()
    return [_to_response(event) for event in events]


@app.get(
    "/api/v1/events/{event_id}",
    response_model=EventResponse,
    dependencies=[Depends(get_current_user)],
)
def get_event(event_id: UUID, session: SessionDep):
    event = session.scalar(
        select(Event).options(selectinload(Event.clips)).where(Event.id == event_id)
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return _to_response(event)


@app.delete(
    "/api/v1/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_event(event_id: UUID, session: SessionDep):
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    # `video_clips.event_id` uses ON DELETE NO ACTION, so remove clips first.
    session.execute(delete(VideoClip).where(VideoClip.event_id == event_id))
    session.delete(event)
    session.commit()
    return None


@app.get("/api/v1/videos/{filename}", dependencies=[Depends(get_current_user)])
def get_video(filename: str):
    video_path = RECORDINGS_DIR / filename
    try:
        if not video_path.resolve().is_relative_to(RECORDINGS_DIR.resolve()):
            raise HTTPException(status_code=400, detail="Invalid path to video")
    except ValueError:
        raise HTTPException(status_code=400, detail="Error at parsing the path") from None
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Clip not found on disk")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename,
        content_disposition_type="inline",
    )


@app.on_event("startup")
def asigura_camera_implicita():
    with next(get_session()) as session:
        camera = session.scalar(select(Camera).where(Camera.name == "test_camera_01"))
        if not camera:
            # `cameras.stream_url` is NOT NULL, UNIQUE and guarded by a CHECK that
            # requires an `rtsp://` URL, so the dev seed must use one.
            noua_camera = Camera(
                name="test_camera_01",
                stream_url="rtsp://127.0.0.1:8554/test_camera_01",
            )
            session.add(noua_camera)
            session.commit()
            print("Auto-seed: camera 'test_camera_01' a fost inserata automat.")
