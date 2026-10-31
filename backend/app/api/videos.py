from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.core.storage import recording_path
from app.db.enums import AuditOutcome, VideoStatus
from app.db.models import VideoClip
from app.services.audit import audit

router = APIRouter(prefix="/videos", tags=["Videos"])


def starts_playback(range_header: str | None) -> bool:
    """True for the request that opens a video, false for the follow-up chunks.

    A browser fetches a video in many `Range` requests (`bytes=0-`, then later parts, and
    more on every seek). Auditing only the first keeps it to about one row per viewing.
    """
    if range_header is None:
        return True
    return range_header.replace(" ", "").lower().startswith("bytes=0-")


@router.get("/{filename}")
def get_video(
    filename: str, request: Request, user: CurrentUserDep, session: SessionDep
) -> FileResponse:
    try:
        video_path = recording_path(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid video file name.") from exc

    # Only files the database knows as a viewable clip; expired, deleted, pending, or
    # files nobody registered are all "not found" (no hint that they exist).
    clip = session.scalar(select(VideoClip).where(VideoClip.filepath == filename))
    if (
        clip is None
        or clip.status != VideoStatus.READY
        or clip.expires_at <= datetime.now(UTC)
        or not video_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="Clip not found.")

    if starts_playback(request.headers.get("range")):
        audit(
            session,
            "clip.view",
            AuditOutcome.SUCCESS,
            user=user,
            resource=("video_clip", str(clip.id)),
            details={"event_id": str(clip.event_id), "file": filename},
        )
        session.commit()

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename,
        content_disposition_type="inline",  # play in the browser instead of downloading
    )
