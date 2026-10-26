import sys
from pathlib import Path

import cv2
import imageio_ffmpeg
import requests
from ultralytics import YOLO

from config import settings
from recorder import Incident, IncidentRecorder
from zone import foot_point, is_in_zone, load_zone

RED, GREEN, BLUE = (0, 0, 255), (0, 255, 0), (255, 0, 0)


def open_video(source):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Could not open video source: {source}")
        sys.exit(1)
    return cap


def get_fps(cap) -> int:
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    # Some streams report 0 or nonsense
    return 30 if fps == 0 or fps > 60 else fps


class FfmpegWriter:
    """Writes H.264 MP4 with the FFmpeg bundled in imageio-ffmpeg.

    OpenCV's own H.264 support depends on the OS and the build; this works the same on
    Windows, macOS and Linux, and H.264 is what every browser's <video> can play.
    """

    def __init__(self, path, fps: int, size: tuple[int, int]) -> None:
        self._frames = imageio_ffmpeg.write_frames(
            str(path),
            size,
            fps=fps,
            codec="libx264",
            pix_fmt_in="bgr24",  # OpenCV frames are BGR
            macro_block_size=2,  # H.264 (yuv420p) only needs an even width and height
            # veryfast: keep up with a live camera; faststart: browsers can play
            # before the whole file has downloaded
            output_params=["-preset", "veryfast", "-movflags", "+faststart"],
        )
        self._frames.send(None)  # starts the FFmpeg process

    def write(self, frame) -> None:
        self._frames.send(frame)

    def release(self) -> None:
        self._frames.close()  # FFmpeg finishes the file when its input closes


def make_writer_factory(fps: int, size: tuple[int, int]):
    def factory(path):
        print(f"[ALARM] Intruder detected! Recording started: {path}")
        return FfmpegWriter(path, fps, size)

    return factory


def detect_people(model, frame):
    """Returns a list of (track_id, (x1, y1, x2, y2)) for every tracked person."""
    results = model.track(frame, persist=True, classes=[0], verbose=False)
    boxes = results[0].boxes
    if boxes is None or boxes.id is None:
        return []
    coords = boxes.xyxy.cpu().numpy().astype(int)
    ids = boxes.id.int().cpu().numpy()
    return [(int(i), tuple(c)) for i, c in zip(ids, coords)]


def draw_person(frame, track_id, box, foot, inside):
    color = RED if inside else GREEN
    x1, y1, x2, y2 = box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.circle(frame, foot, 5, color, -1)
    cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def build_config_snapshot(zone, fps: int) -> dict:
    """The settings this run detects with; stored on every event as evidence."""
    return {
        "schema_version": 1,
        "model_ref": Path(settings.model_path).name,
        "detection_config": {
            "schema_version": 1,
            "region": {
                "type": "polygon",
                "match_rule": "bottom_center",  # foot_point(): bottom-centre of the box
                "points": zone.reshape(-1, 2).tolist(),
            },
        },
        "settings": {
            "min_presence_seconds": settings.min_presence_seconds,
            "pre_roll_seconds": settings.pre_roll_seconds,
            "post_roll_seconds": settings.post_roll_seconds,
            "fps": fps,
        },
    }


def report_incident(incident: Incident, config_snapshot: dict) -> None:
    payload = {
        "camera_id": settings.camera_id,
        "video_path": incident.clip.name,
        "started_at": incident.started_at.isoformat(),
        "last_person_seen_at": incident.last_person_seen_at.isoformat(),
        "closed_at": incident.closed_at.isoformat(),
        "end_reason": incident.end_reason,
        "config_snapshot": config_snapshot,
    }
    # Without a real size and time span the backend keeps the clip `pending`.
    size = incident.clip.stat().st_size if incident.clip.exists() else 0
    if size > 0 and incident.recorded_end_at > incident.recorded_start_at:
        payload["size_bytes"] = size
        payload["recorded_start_at"] = incident.recorded_start_at.isoformat()
        payload["recorded_end_at"] = incident.recorded_end_at.isoformat()

    try:
        response = requests.post(
            f"{settings.api_url}/events",
            json=payload,
            headers={"X-API-Key": settings.api_key},
            timeout=5.0,
        )
        response.raise_for_status()
        print(f"[API] Saved incident: {incident.clip.name}")
    except requests.exceptions.HTTPError as e:
        print(f"[API Error] {e.response.status_code} for {incident.clip.name}: {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"[API Error] Could not reach the API for {incident.clip.name}: {e}")


def main() -> None:
    model = YOLO(settings.model_path)
    cap = open_video(settings.capture_source())
    fps = get_fps(cap)
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    zone = load_zone(settings.zone_config)
    config_snapshot = build_config_snapshot(zone, fps)

    recorder = IncidentRecorder(
        writer_factory=make_writer_factory(fps, size),
        clips_dir=settings.clips_dir,
        pre_roll_frames=round(settings.pre_roll_seconds * fps),
        post_roll_frames=round(settings.post_roll_seconds * fps),
        min_presence_frames=round(settings.min_presence_seconds * fps),
    )

    paused = False
    end_reason = "manual_stop"  # why a clip still recording at exit was cut short
    print("[INFO] Monitoring system is active. Press 'q' to exit, 'p' to pause.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[INFO] Video stream ended.")
            end_reason = "stream_lost"
            break

        raw_frame = frame.copy()  # clean copy for saving, without drawings
        cv2.polylines(frame, [zone], isClosed=True, color=BLUE, thickness=2)

        intruders = 0
        for track_id, box in detect_people(model, frame):
            foot = foot_point(box)
            inside = is_in_zone(zone, foot)
            intruders += inside
            draw_person(frame, track_id, box, foot, inside)
            if settings.debug:
                print(f"[DEBUG] ID {track_id}: box={box} foot={foot} inside={inside}")

        finished = recorder.update(raw_frame, someone_in_zone=intruders > 0)
        if finished:
            print(f"[INFO] Incident saved: {finished.clip}")
            report_incident(finished, config_snapshot)

        if settings.show_window:
            if recorder.is_recording:
                cv2.putText(frame, "REC", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, RED, 3)
            cv2.imshow("Restricted Zone Monitoring", frame)
            # 'q' = exit, 'p' = pause/resume, any other key while paused = next frame
            key = cv2.waitKey(0 if paused else 1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("p"):
                paused = not paused

    finished = recorder.close(end_reason)  # don't lose a clip if we quit mid-incident
    if finished:
        print(f"[INFO] Incident saved: {finished.clip}")
        report_incident(finished, config_snapshot)
    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Program finished.")


if __name__ == "__main__":
    main()
