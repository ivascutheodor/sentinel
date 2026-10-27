from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/videos", tags=["Videos"])
RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "recordings"


@router.get("/{filename}")
def get_video(filename: str) -> FileResponse:
    try:
        video_path = (RECORDINGS_DIR / filename).resolve()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Error at parsing the path") from exc
    if not video_path.is_relative_to(RECORDINGS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path to video")
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="Clip not found on disk")
    return FileResponse(path=video_path, media_type="video/mp4", filename=filename)
