from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import AdminDep, SessionDep, get_current_user, verify_worker_key
from app.db.enums import AuditOutcome, CaptureState, EventType, VideoStatus
from app.db.models import Camera, Event, VideoClip
from app.schemas.events import EventCreate, EventPage, EventResponse
from app.services.audit import audit
from app.services.clip_files import delete_clips
from app.services.manifests import ManifestError, verify_manifest
from app.services.system_settings import get_system_settings

router = APIRouter(prefix="/events", tags=["Events"])

# Stored when the worker sends no snapshot; satisfies the `events.config_snapshot` CHECK.
DEFAULT_CONFIG_SNAPSHOT: dict = {
    "schema_version": 1,
    "model_ref": "yolo11n.pt",
    "detection_config": {"schema_version": 1, "region": None},
    "settings": {},
}

# Loaded with every event we return: its clips, and its camera for `camera_name`.
EVENT_LOAD_OPTIONS = (selectinload(Event.clips), selectinload(Event.camera))


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a finished incident clip (worker only)",
    dependencies=[Depends(verify_worker_key)],
)
def create_event(event: EventCreate, session: SessionDep) -> Event:
    camera = session.scalar(select(Camera).where(Camera.name == event.camera_id))
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {event.camera_id!r} not found.")

    sha256 = None
    if event.source_manifest_ref is not None:
        try:
            sha256 = verify_manifest(
                event.source_manifest_ref, event.camera_id, event.video_path, event.size_bytes
            )
        except ManifestError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Read when the clip is saved; changing retention later does not rewrite existing clips.
    retention = timedelta(days=get_system_settings(session).retention_days)
    now = datetime.now(UTC)
    # The `video_clips` CHECK only allows `ready` once the file's size and time span are known.
    is_ready = event.size_bytes is not None and event.recorded_start_at is not None
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
            event.config_snapshot.model_dump(mode="json")
            if event.config_snapshot
            else DEFAULT_CONFIG_SNAPSHOT
        ),
        clips=[
            VideoClip(
                part_number=1,
                # Without a manifest the column (NOT NULL, UNIQUE) gets a placeholder that
                # can't be mistaken for a real manifests/<name>.json key.
                source_manifest_ref=event.source_manifest_ref or f"placeholder/{uuid4()}",
                sha256=sha256,
                filepath=event.video_path,
                status=VideoStatus.READY if is_ready else VideoStatus.PENDING,
                size_bytes=event.size_bytes,
                recorded_start_at=event.recorded_start_at,
                recorded_end_at=event.recorded_end_at,
                source_ready_at=now if is_ready else None,
                expires_at=now + retention,
            )
        ],
    )
    session.add(new_event)
    try:
        session.commit()
    except IntegrityError as exc:
        # e.g. the same clip file posted twice (`video_clips.filepath` is unique)
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event conflicts with existing data or database constraints.",
        ) from exc
    session.refresh(new_event)
    return new_event


@router.get(
    "",
    response_model=EventPage,
    dependencies=[Depends(get_current_user)],
)
def list_events(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    camera_id: UUID | None = None,
    started_from: Annotated[
        AwareDatetime | None, Query(description="Inclusive. Use `Z` or `%2B` for `+`.")
    ] = None,
    started_to: Annotated[AwareDatetime | None, Query(description="Exclusive.")] = None,
) -> EventPage:
    if started_from is not None and started_to is not None and started_from >= started_to:
        raise HTTPException(status_code=422, detail="started_from must be before started_to.")

    # Shared by the count and the page, so `total` always matches what can be paged through.
    filters = []
    if camera_id is not None:
        filters.append(Event.camera_id == camera_id)
    if started_from is not None:
        filters.append(Event.started_at >= started_from)
    if started_to is not None:
        filters.append(Event.started_at < started_to)

    total = session.scalar(select(func.count()).select_from(Event).where(*filters))
    statement = (
        select(Event)
        .where(*filters)
        .options(*EVENT_LOAD_OPTIONS)
        # `id` breaks ties, so an event can't appear on two pages or on none.
        .order_by(Event.started_at.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = session.scalars(statement).all()
    return EventPage(
        items=[EventResponse.model_validate(event) for event in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    dependencies=[Depends(get_current_user)],
)
def get_event(event_id: UUID, session: SessionDep) -> Event:
    event = session.scalar(select(Event).where(Event.id == event_id).options(*EVENT_LOAD_OPTIONS))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event's recordings (admin only)",
)
def delete_event(event_id: UUID, session: SessionDep, admin: AdminDep) -> None:
    """Removes the video and manifest files; the event and clip rows stay as the record.

    The event stays in `GET /events` with its clips `deleted` ("recording deleted"), so the
    history of who was where, and who deleted the footage, is kept. Deleting again is safe:
    clips already `deleted` are skipped, and clips left `deleting` are retried.
    """
    event = session.scalar(
        select(Event).where(Event.id == event_id).options(selectinload(Event.clips))
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    clips = [clip for clip in event.clips if clip.status != VideoStatus.DELETED]
    if not clips:
        return
    failed = delete_clips(session, clips)
    audit(
        session,
        "event.delete",
        AuditOutcome.SUCCESS if failed == 0 else AuditOutcome.FAILURE,
        user=admin,
        resource=("event", str(event_id)),
        details={"clips": len(clips), "failed": failed},
    )
    session.commit()
    if failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The recording could not be removed, probably because it is in use. "
                "It is marked for deletion; try again."
            ),
        )
