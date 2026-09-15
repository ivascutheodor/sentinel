import cv2
import json
import numpy as np
from ultralytics import YOLO
from collections import deque
from datetime import datetime


# ==========================================
# 1. INITIAL CONFIGURATION
# ==========================================
# Load the YOLO model on the standard classes (will automatically use CPU or GPU)

VIDEO_PATH = r"E:\cctv_lockers\data\clips\filmare_test_3.mp4"
CONFIG_PATH = r"config_zona.json"

model = YOLO("yolo11n.pt")

# Open the camera (0 for the built-in webcam, or set an IP stream / video file path)
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print(f"[ERROR] Could not open video file: {VIDEO_PATH}")
    exit(1)

# Grab the camera settings for the VideoWriter
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))

# If the webcam doesn't report the FPS correctly, force it to a standard value
if fps == 0 or fps > 60:
    fps = 30

with open(CONFIG_PATH, "r") as f:
    zone_polygon = json.load(f)
# Define the polygon (Restricted Zone) - example with 4 points (you can adjust them)
zone_polygon = np.array(zone_polygon, np.int32).reshape((-1,1,2))
# ==========================================
# 2. STATE MACHINE VARIABLES
# ==========================================
FRAMES_5_SECONDS = 5 * fps                 # 150 frames (at 30 FPS)
initial_buffer = deque(maxlen=FRAMES_5_SECONDS)

paused = False                            # Manual pause for frame-by-frame inspection
is_recording = False                      # System state
post_roll_counter = 0                     # Countdown counter
writer = None                             # Variable for the MP4 file
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Video codec, i.e. the algorithm used to encode/decode the video, fourcc = four character code

print("[INFO] Monitoring system is active. Press 'q' to exit.")

# ==========================================
# 3. MAIN PROCESSING LOOP
# ==========================================
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("[INFO] Video stream ended. Exiting loop.")
        break

    # [A] COPY THE FRAME FOR RAW SAVING (Clean, without any graphics)
    raw_frame = frame.copy()

    # Add the clean frame to the buffer (UNCONDITIONALLY, always runs in the background)
    initial_buffer.append(raw_frame)

    # Counter for the number of people INSIDE THE POLYGON in this frame
    current_intruders = 0

    # [B] RUN THE AI ON THE CURRENT FRAME
    # persist=True for tracking, classes=[0] for people only
    results = model.track(frame, persist=True, classes=[0], verbose=False)

    # [C] DRAW THE POLYGON ON THE LIVE SCREEN (in blue)
    cv2.polylines(frame, [zone_polygon], isClosed=True, color=(255, 0, 0), thickness=2)

    # Process detections if any exist
    if results[0].boxes is not None and results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.int().cpu().numpy()

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = map(int, box)

            # Compute the person's "feet"
            foot_x = int((x1 + x2) / 2)
            foot_y = y2

            # Check whether the feet are inside the polygon
            # pointPolygonTest returns > 0 (inside), 0 (on the edge), < 0 (outside)
            test_result = cv2.pointPolygonTest(zone_polygon, (foot_x, foot_y), False)

            if test_result >= 0:
                # The person is INSIDE the zone
                current_intruders += 1
                rectangle_color = (0, 0, 255) # Red for alert
            else:
                # The person is OUTSIDE the zone
                rectangle_color = (0, 255, 0) # Green for safe

            # Draw on the LIVE frame (NOT on raw_frame)
            cv2.rectangle(frame, (x1, y1), (x2, y2), rectangle_color, 2)
            cv2.circle(frame, (foot_x, foot_y), 5, rectangle_color, -1)
            cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, rectangle_color, 2)

            # [DEBUG] Show the exact numeric value of pointPolygonTest next to the foot point
            cv2.putText(frame, f"dist={test_result:.1f}", (foot_x + 10, foot_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, rectangle_color, 2)
            print(f"[DEBUG] ID {track_id}: box=({x1},{y1})-({x2},{y2}) foot=({foot_x},{foot_y}) dist={test_result:.2f}")

    # ==========================================
    # 4. SAVING LOGIC (STATE MACHINE)
    # ==========================================

    # STATE 1: We have intruders in the zone
    if current_intruders > 0:
        if not is_recording:
            # TRIGGER: A new incident starts
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            file_name = f"incident_{timestamp}.mp4"
            writer = cv2.VideoWriter(file_name, fourcc, fps, (frame_width, frame_height))

            # Flush the past from RAM to disk
            for past_frame in initial_buffer:
                writer.write(past_frame)

            print(f"[ALARM] Intruder detected! Recording started: {file_name}")
            is_recording = True
        else:
            # ONGOING: The incident continues, write the new frame (RAW) directly to disk
            writer.write(raw_frame)

        # Keep the post-roll counter full, since intruders are still here
        post_roll_counter = FRAMES_5_SECONDS

    # STATE 2: We no longer have intruders in the zone
    else:
        if is_recording:
            # POST-ROLL: The intruder left, but we still need to save 5 more seconds
            if post_roll_counter > 0:
                writer.write(raw_frame)
                post_roll_counter -= 1
            else:
                # FINALIZE: The 5 seconds have passed, close the file
                writer.release()
                is_recording = False
                print("[INFO] Incident saved successfully. System back to standby mode.")

    # ==========================================
    # 5. LIVE DISPLAY AND STOPPING
    # ==========================================
    # Show the processed frame on screen for the security guard
    # Put a red "REC" indicator on screen (visual only, on the monitor) while recording
    if is_recording:
        cv2.putText(frame, "• REC", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    cv2.imshow("Restricted Zone Monitoring", frame)

    # Press 'q' = exit, 'p' = pause/resume, any other key while paused = advance one frame
    key = cv2.waitKey(0 if paused else 1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('p'):
        paused = not paused

# ==========================================
# 6. CLEANUP ON EXIT
# ==========================================
# Properly close the video file if the user pressed 'q' in the middle of an alarm
if is_recording and writer is not None:
    writer.release()

cap.release()
cv2.destroyAllWindows()
print("[INFO] Program finished successfully. Code = 0.")
