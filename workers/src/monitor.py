import sys

import cv2
from ultralytics import YOLO

from config import settings
from recorder import IncidentRecorder
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


def make_cv2_writer_factory(fps: int, size: tuple[int, int]):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    def factory(path):
        print(f"[ALARM] Intruder detected! Recording started: {path}")
        return cv2.VideoWriter(str(path), fourcc, fps, size)

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


def main() -> None:
    model = YOLO(settings.model_path)
    cap = open_video(settings.capture_source())
    fps = get_fps(cap)
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    zone = load_zone(settings.zone_config)

    recorder = IncidentRecorder(
        writer_factory=make_cv2_writer_factory(fps, size),
        clips_dir=settings.clips_dir,
        pre_roll_frames=round(settings.pre_roll_seconds * fps),
        post_roll_frames=round(settings.post_roll_seconds * fps),
        min_presence_frames=round(settings.min_presence_seconds * fps),
    )

    paused = False
    print("[INFO] Monitoring system is active. Press 'q' to exit, 'p' to pause.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("[INFO] Video stream ended.")
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
            print(f"[INFO] Incident saved: {finished}")

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

    finished = recorder.close()  # don't lose a clip if we quit mid-incident
    if finished:
        print(f"[INFO] Incident saved: {finished}")
    cap.release()
    cv2.destroyAllWindows()
    print("[INFO] Program finished.")


if __name__ == "__main__":
    main()
