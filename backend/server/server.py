from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

# Make the sibling `app` package importable no matter where this file is launched from.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.enums import CaptureState, EventType, VideoStatus  # noqa: E402
from app.db.models import Camera, Event, VideoClip  # noqa: E402
from app.db.session import get_session  # noqa: E402

SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(title="Sentinel backend API", version="1.0.0")

PROJECT_ROOT = BACKEND_DIR.parent
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RETENTION_DAYS = 7
DEFAULT_MODEL_REF = "yolo11n.pt"

# Minimal but valid `events.config_snapshot` payload. The JSONB CHECK on the
# `events` table requires `schema_version`, `model_ref`, `detection_config` and
# `settings`; replace this with a real snapshot as soon as the worker sends one.
DEFAULT_CONFIG_SNAPSHOT: dict = {
    "schema_version": 1,
    "model_ref": DEFAULT_MODEL_REF,
    "detection_config": {"schema_version": 1, "region": None},
    "settings": {},
}


class EventCreate(BaseModel):
    camera_id: str
    video_path: str


class EventResponse(BaseModel):
    id: UUID
    camera_id: UUID
    video_path: str | None
    created_at: datetime


def _to_response(event: Event) -> EventResponse:
    video_path = event.clips[0].filepath if event.clips else None
    return EventResponse(
        id=event.id,
        camera_id=event.camera_id,
        video_path=video_path,
        created_at=event.created_at,
    )


def _resolve_camera(session: Session, camera_id: str) -> Camera:
    camera = session.scalar(select(Camera).where(Camera.name == camera_id))
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id!r} not found.",
        )
    return camera


@app.post(
    "/api/v1/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Events"],
    summary="Saves a new indexed video",
)
def create_event_db(event: EventCreate, session: SessionDep):
    camera = _resolve_camera(session, event.camera_id)

    now = datetime.now(UTC)
    new_event = Event(
        camera_id=camera.id,
        event_type=EventType.PERSON_PRESENCE,
        status=CaptureState.COMPLETED,
        started_at=now,
        last_person_seen_at=now,
        closed_at=now,
        end_reason="person_absent",
        config_snapshot=DEFAULT_CONFIG_SNAPSHOT,
    )
    session.add(new_event)
    session.flush()  # populate new_event.id before linking the clip

    clip = VideoClip(
        event_id=new_event.id,
        part_number=1,
        source_manifest_ref=f"manifests/{uuid4()}.json",
        filepath=event.video_path,
        status=VideoStatus.PENDING,
        expires_at=now + timedelta(days=DEFAULT_RETENTION_DAYS),
    )
    session.add(clip)
    session.commit()
    session.refresh(new_event)

    return _to_response(new_event)


@app.get("/api/v1/events", response_model=list[EventResponse])
def get_all_events(session: SessionDep):
    events = session.scalars(select(Event).options(selectinload(Event.clips))).all()
    return [_to_response(event) for event in events]


@app.get("/api/v1/events/{event_id}", response_model=EventResponse)
def get_event(event_id: UUID, session: SessionDep):
    event = session.scalar(
        select(Event).options(selectinload(Event.clips)).where(Event.id == event_id)
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return _to_response(event)


@app.delete("/api/v1/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: UUID, session: SessionDep):
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    # `video_clips.event_id` uses ON DELETE NO ACTION, so remove clips first.
    session.execute(delete(VideoClip).where(VideoClip.event_id == event_id))
    session.delete(event)
    session.commit()
    return None


@app.get("/api/v1/videos/{filename}")
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

