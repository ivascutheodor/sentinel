"""Settings for the worker. Override any of them with environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

WORKERS_DIR = Path(__file__).resolve().parent.parent

# Reads workers/.env no matter which folder you run the script from.
# Variables already set in the shell win over the file.
load_dotenv(WORKERS_DIR / ".env")


def _resolve(value: str) -> Path:
    """Relative paths in .env are relative to the workers/ folder."""
    path = Path(value)
    return path if path.is_absolute() else WORKERS_DIR / path


@dataclass(frozen=True)
class Settings:
    # Video file path, camera index (e.g. "0") or stream URL (e.g. rtsp://...)
    video_source: str = os.getenv("SENTINEL_VIDEO_SOURCE", str(WORKERS_DIR.parent / "recordings" / "test1.mp4"))
    zone_config: Path = _resolve(os.getenv("SENTINEL_ZONE_CONFIG", "src/config_zona.json"))
    model_path: str = str(_resolve(os.getenv("SENTINEL_MODEL", "yolo11n.pt")))
    clips_dir: Path = _resolve(os.getenv("SENTINEL_CLIPS_DIR", "../recordings"))

    #example, should be changed 
    api_url: str = os.getenv("SENTINEL_API_URL", "http://127.0.0.1:8000/api/v1")
    camera_id: str = os.getenv("SENTINEL_CAMERA_ID", "test_camera_01")


    pre_roll_seconds: float = float(os.getenv("SENTINEL_PRE_ROLL_SECONDS", "5"))
    post_roll_seconds: float = float(os.getenv("SENTINEL_POST_ROLL_SECONDS", "5"))
    # Someone must stay in the zone this long before an incident is recorded
    min_presence_seconds: float = float(os.getenv("SENTINEL_MIN_PRESENCE_SECONDS", "2"))

    show_window: bool = os.getenv("SENTINEL_SHOW_WINDOW", "1") == "1"
    debug: bool = os.getenv("SENTINEL_DEBUG", "0") == "1"

    def capture_source(self) -> str | int:
        """OpenCV wants an int for camera indexes and a string for files/URLs."""
        if self.video_source.isdigit():
            return int(self.video_source)
        local_file = WORKERS_DIR / self.video_source
        return str(local_file) if local_file.exists() else self.video_source


settings = Settings()
