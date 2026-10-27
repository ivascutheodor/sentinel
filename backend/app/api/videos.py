from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_user

router = APIRouter(prefix="/videos", tags=["Videos"], dependencies=[Depends(get_current_user)])
RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "recordings"


@router.get("/{filename}")
def get_video(filename: str) -> FileResponse:
    # Only a bare file name: no folders, no NUL byte (Windows paths accept some of these
    # without raising, so check explicitly instead of relying on resolve()).
    if "\x00" in filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Invalid video file name.")
    video_path = (RECORDINGS_DIR / filename).resolve()
    # Catches symlinks inside recordings/ that point elsewhere.
    if not video_path.is_relative_to(RECORDINGS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path to video.")
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Clip not found on disk.")
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename,
        content_disposition_type="inline",  # play in the browser instead of downloading
    )
