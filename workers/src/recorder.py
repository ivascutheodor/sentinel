"""Decides when to start and stop saving an incident clip.

Kept free of YOLO and the screen so it can be tested with fake frames.
"""

from collections import deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from config import settings
import requests

class VideoWriter(Protocol):
    def write(self, frame: Any) -> None: ...
    def release(self) -> None: ...


class IncidentRecorder:
    """Call `update()` once per frame.

    - The last `pre_roll_frames` are always kept in RAM.
    - Someone must be in the zone for `min_presence_frames` in a row to start an incident;
      the buffered frames are then written to disk first.
    - After the zone empties, `post_roll_frames` more are saved before the clip is closed.
    """

    def __init__(
        self,
        writer_factory: Callable[[Path], VideoWriter],
        clips_dir: Path,
        pre_roll_frames: int,
        post_roll_frames: int,
        min_presence_frames: int,
    ) -> None:
        self._writer_factory = writer_factory
        self._clips_dir = clips_dir
        self._post_roll_frames = post_roll_frames
        self._min_presence_frames = min_presence_frames
        self._buffer: deque[Any] = deque(maxlen=pre_roll_frames)
        self._writer: VideoWriter | None = None
        self._presence_counter = 0
        self._post_roll_counter = 0
        self.current_clip: Path | None = None

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    def update(self, raw_frame: Any, someone_in_zone: bool) -> Path | None:
        """Returns the path of a clip when one has just been finished, otherwise None."""
        self._buffer.append(raw_frame)

        if someone_in_zone:
            self._presence_counter += 1
            self._post_roll_counter = self._post_roll_frames
            if self._writer is not None:
                self._writer.write(raw_frame)
            elif self._presence_counter >= self._min_presence_frames:
                self._start()
                #payload is sent to the server via API 
                try:
                    payload = {
                        "camera_id": settings.camera_id,
                        "status": "capturing",
                        "message": "Person insider the perimeter!"
                    }
                    url = f"{settings.api_url}/events"
                    requests.post(url, json=payload, timeout=2.0)
                    print("[API] Recording has started.")
                except requests.exceptions.RequestException as e:
                    print(f"[API Eroare] Backend is down, but recording is still on: {e}")
            return None

        self._presence_counter = 0
        if self._writer is None:
            return None

        if self._post_roll_counter > 0:
            self._writer.write(raw_frame)
            self._post_roll_counter -= 1
            return None
        return self._finish()


    def close(self) -> Path | None:
        return self._finish() if self._writer is not None else None

    def _start(self) -> None:
        self._clips_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_clip = self._clips_dir / f"incident_{timestamp}.mp4"
        self._writer = self._writer_factory(self.current_clip)
        for past_frame in self._buffer:  # includes the current frame
            self._writer.write(past_frame)

    def _finish(self) -> Path | None:
        assert self._writer is not None
        self._writer.release()
        clip, self._writer, self.current_clip = self.current_clip, None, None
        if clip is not None:
            try:
                payload = {
                    "camera_id": settings.camera_id,
                    "video_path": str(clip)  # file path
                }
                url = f"{settings.api_url}/events"
                # Folosim POST (sau PATCH, iti va confirma colegul cand are ruta gata)
                requests.post(url, json=payload, timeout=2.0)
                print(f"[API] Saved incident. Saved clip at: {clip}")
            except requests.exceptions.RequestException as e:
                print(f"[API Error] Error, couldn't save the clip: {e}")
        return clip
