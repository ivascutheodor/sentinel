from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import SessionDep, get_current_user, verify_worker_key
from app.db.enums import CaptureState, EventType, VideoStatus
from app.db.models import Camera, Event, VideoClip
from app.schemas.events import EventCreate, EventResponse

router = APIRouter(prefix="/events", tags=["Events"])

DEFAULT_RETENTION_DAYS = 7

# Stored when the worker sends no snapshot; satisfies the `events.config_snapshot` CHECK.
DEFAULT_CONFIG_SNAPSHOT: dict = {
    "schema_version": 1,
    "model_ref": "yolo11n.pt",
    "detection_config": {"schema_version": 1, "region": None},
    "settings": {},
}


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
                source_manifest_ref=f"manifests/{uuid4()}.json",
                filepath=event.video_path,
                status=VideoStatus.READY if is_ready else VideoStatus.PENDING,
                size_bytes=event.size_bytes,
                recorded_start_at=event.recorded_start_at,
                recorded_end_at=event.recorded_end_at,
                source_ready_at=now if is_ready else None,
                expires_at=now + timedelta(days=DEFAULT_RETENTION_DAYS),
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
    response_model=list[EventResponse],
    dependencies=[Depends(get_current_user)],
)
def list_events(session: SessionDep) -> list[Event]:
    statement = (
        select(Event).options(selectinload(Event.clips)).order_by(Event.created_at.desc(), Event.id)
    )
    return list(session.scalars(statement).all())


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    dependencies=[Depends(get_current_user)],
)
def get_event(event_id: UUID, session: SessionDep) -> Event:
    event = session.scalar(
        select(Event).where(Event.id == event_id).options(selectinload(Event.clips))
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user)],
)
def delete_event(event_id: UUID, session: SessionDep) -> None:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    # `video_clips.event_id` uses ON DELETE NO ACTION, so remove clips first.
    # The video file itself stays on disk (see CLAUDE.md, "What is left").
    session.execute(delete(VideoClip).where(VideoClip.event_id == event_id))
    session.delete(event)
    session.commit()
