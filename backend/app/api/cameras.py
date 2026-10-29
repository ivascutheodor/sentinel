from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminDep, SessionDep, get_current_user
from app.db.enums import AuditOutcome
from app.db.models import Camera
from app.schemas.cameras import CameraCreate, CameraDetail, CameraSummary, CameraUpdate
from app.services.audit import audit

router = APIRouter(prefix="/cameras", tags=["Cameras"])


def camera_or_404(session: SessionDep, camera_id: UUID) -> Camera:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    return camera


def commit_or_409(session: SessionDep) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        # `uq_cameras_name_lower` or the unique `stream_url`
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A camera with this name or stream URL already exists.",
        ) from exc


@router.get("", response_model=list[CameraSummary], dependencies=[Depends(get_current_user)])
def list_cameras(session: SessionDep) -> list[Camera]:
    return list(session.scalars(select(Camera).order_by(Camera.name, Camera.id)).all())


@router.get("/{camera_id}", response_model=CameraDetail)
def get_camera(camera_id: UUID, session: SessionDep, admin: AdminDep) -> Camera:
    return camera_or_404(session, camera_id)


@router.post("", response_model=CameraDetail, status_code=status.HTTP_201_CREATED)
def create_camera(body: CameraCreate, session: SessionDep, admin: AdminDep) -> Camera:
    camera = Camera(**body.model_dump(mode="json"))
    session.add(camera)
    commit_or_409(session)
    audit(session, "camera.create", AuditOutcome.SUCCESS, user=admin, resource=camera_ref(camera))
    session.commit()
    return camera


@router.patch("/{camera_id}", response_model=CameraDetail)
def update_camera(
    camera_id: UUID, body: CameraUpdate, session: SessionDep, admin: AdminDep
) -> Camera:
    camera = camera_or_404(session, camera_id)
    # `exclude_unset`: only what the request sent, so a missing field is left alone and an
    # explicit `"location": null` clears it.
    changes = body.model_dump(mode="json", exclude_unset=True)
    if not changes:
        return camera
    for field, value in changes.items():
        setattr(camera, field, value)
    camera.updated_at = datetime.now(UTC)  # no `updated_at` trigger in the database yet
    commit_or_409(session)

    details: dict = {"fields": sorted(changes)}
    if "is_enabled" in changes:
        details["is_enabled"] = changes["is_enabled"]
    audit(
        session,
        "camera.update",
        AuditOutcome.SUCCESS,
        user=admin,
        resource=camera_ref(camera),
        details=details,
    )
    session.commit()
    return camera


def camera_ref(camera: Camera) -> tuple[str, str]:
    return ("camera", str(camera.id))
