from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import Camera, Event, VideoClip
from app.db.session import get_session
from app.schemas.events import EventCreate, EventResponse

router = APIRouter(prefix="/events", tags=["Events"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event_db(event: EventCreate, db: DatabaseSession) -> Event:
    if db.get(Camera, event.camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found.")

    db_event = Event(
        **event.model_dump(exclude={"clips", "config_snapshot"}),
        config_snapshot=event.config_snapshot.model_dump(mode="json"),
        clips=[VideoClip(**clip.model_dump()) for clip in event.clips],
    )
    db.add(db_event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Event conflicts with existing data or database constraints.",
        ) from exc
    db.refresh(db_event)
    return db_event


@router.get("", response_model=list[EventResponse])
def get_all_events(db: DatabaseSession) -> list[Event]:
    statement = (
        select(Event).options(selectinload(Event.clips)).order_by(Event.created_at.desc(), Event.id)
    )
    return list(db.scalars(statement).all())


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: UUID, db: DatabaseSession) -> Event:
    statement = select(Event).where(Event.id == event_id).options(selectinload(Event.clips))
    event = db.scalar(statement)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: UUID, db: DatabaseSession) -> None:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    db.delete(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Event has related records and cannot be deleted.",
        ) from exc
