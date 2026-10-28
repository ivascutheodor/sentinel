"""Decides when to start and stop saving an incident clip.

Kept free of YOLO, the screen and the API so it can be tested with fake frames.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


class VideoWriter(Protocol):
    def write(self, frame: Any) -> None: ...
    def release(self) -> None: ...


@dataclass(frozen=True)
class Incident:
    """A finished clip and the moments that describe it (all timezone-aware UTC)."""

    clip: Path
    started_at: datetime  # first frame of the presence streak that triggered recording
    last_person_seen_at: datetime  # last frame with someone in the zone
    closed_at: datetime  # when the clip was closed
    end_reason: str  # "person_absent", or why it was cut short (see the `events` CHECK)
    recorded_start_at: datetime  # first frame in the file (includes pre-roll)
    recorded_end_at: datetime  # last frame in the file (includes post-roll)
    frame_count: int  # frames written to the file


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IncidentRecorder:
    """Call `update()` once per frame.

    - The last `pre_roll_frames` are always kept in RAM.
    - Someone must be in the zone for `min_presence_frames` in a row to start an incident;
      the buffered frames are then written to disk first.
    - After the zone empties, `post_roll_frames` more are saved before the clip is closed.

    Frame times come from `clock` when the frame is processed. For a live camera that is
    the real time; for a video file it is when the worker read the frame.
    """

    def __init__(
        self,
        writer_factory: Callable[[Path], VideoWriter],
        clips_dir: Path,
        pre_roll_frames: int,
        post_roll_frames: int,
        min_presence_frames: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._writer_factory = writer_factory
        self._clips_dir = clips_dir
        self._post_roll_frames = post_roll_frames
        self._min_presence_frames = min_presence_frames
        self._clock = clock
        # At least 1, so the frame that triggers the recording is always written.
        self._buffer: deque[tuple[datetime, Any]] = deque(maxlen=max(pre_roll_frames, 1))
        self._writer: VideoWriter | None = None
        self._presence_counter = 0
        self._post_roll_counter = 0
        self.current_clip: Path | None = None

        self._presence_started_at: datetime | None = None
        self._started_at: datetime | None = None
        self._last_person_seen_at: datetime | None = None
        self._recorded_start_at: datetime | None = None
        self._recorded_end_at: datetime | None = None
        self._frame_count = 0

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    def update(self, raw_frame: Any, someone_in_zone: bool) -> Incident | None:
        """Returns the incident when its clip has just been finished, otherwise None."""
        now = self._clock()
        self._buffer.append((now, raw_frame))

        if someone_in_zone:
            if self._presence_counter == 0:
                self._presence_started_at = now
            self._presence_counter += 1
            self._post_roll_counter = self._post_roll_frames
            if self._writer is not None:
                self._write(now, raw_frame)
                self._last_person_seen_at = now
            elif self._presence_counter >= self._min_presence_frames:
                self._start(now)
            return None

        self._presence_counter = 0
        if self._writer is None:
            return None

        if self._post_roll_counter > 0:
            self._write(now, raw_frame)
            self._post_roll_counter -= 1
            return None
        return self._finish("person_absent")

    def close(self, end_reason: str = "manual_stop") -> Incident | None:
        """Saves a clip still in progress; `end_reason` says why it was cut short."""
        return self._finish(end_reason) if self._writer is not None else None

    def _start(self, now: datetime) -> None:
        self._clips_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_clip = self._clips_dir / f"incident_{timestamp}.mp4"
        self._writer = self._writer_factory(self.current_clip)
        self._started_at = self._presence_started_at
        self._last_person_seen_at = now
        self._recorded_start_at = self._buffer[0][0]
        self._frame_count = 0
        for frame_time, past_frame in self._buffer:  # includes the current frame
            self._write(frame_time, past_frame)

    def _write(self, frame_time: datetime, frame: Any) -> None:
        assert self._writer is not None
        self._writer.write(frame)
        self._recorded_end_at = frame_time
        self._frame_count += 1

    def _finish(self, end_reason: str) -> Incident:
        assert self._writer is not None and self.current_clip is not None
        self._writer.release()
        incident = Incident(
            clip=self.current_clip,
            started_at=self._started_at,
            last_person_seen_at=self._last_person_seen_at,
            closed_at=self._clock(),
            end_reason=end_reason,
            recorded_start_at=self._recorded_start_at,
            recorded_end_at=self._recorded_end_at,
            frame_count=self._frame_count,
        )
        self._writer, self.current_clip = None, None
        return incident
