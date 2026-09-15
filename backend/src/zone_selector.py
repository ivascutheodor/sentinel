import cv2
import json
import numpy as np

VIDEO_PATH = r"E:\cctv_lockers\data\clips\filmare_test_3.mp4"
CONFIG_PATH = r"config_zona.json"

cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print("Error: Could not open video source.")
    exit()

#ret is a binary number that shows whether the read succeeded or not
ret, first_frame = cap.read()
#close the connection to the video, we only need a single static image, not all of it
cap.release()
if not ret:
    print("Error reading frame.")
    exit(1)

#the list must be initialized before it is used
point_list = []

def mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        param.append((x,y))

    elif event == cv2.EVENT_RBUTTONDOWN:
        if len(param) > 0:
            param.pop()

cv2.namedWindow("Calibration")
cv2.setMouseCallback("Calibration", mouse, param=point_list)


print("=== CALIBRATION CONTROLS ===")
print("Left Click   : Add point")
print("Right Click  : Remove last point (Undo)")
print("Key 'c'      : Reset all points")
print("Key 's'      : Save to config_zona.json and close")
print("Key 'q'      : Exit without saving")


while True:
    #make a copy so we don't mark up the original frame
    copy_frame = first_frame.copy()
    for point in point_list:
        #draw circles where we clicked to get visual feedback
        #5 is the circle radius in pixels
        #(0,0,255) is the color, in BGR format
        #-1 means the circle is filled
        cv2.circle(copy_frame, point, 5, (0,0,255), -1)

    if len(point_list) >= 2:
        #cv.polylines, the function that draws the lines needs a np array
        #reshape(-1,1,2) => -1 means the algorithm decides how many rows the matrix has, 1 means how many columns, and 2 means how many variables: x, y
        points_array = np.array(point_list, np.int32).reshape(-1, 1, 2)
        #isClosed=False because if we drew the 3rd point, it would connect to the first one and form a triangle. use True in the production version once we already have the coordinates
        #[points_array] is a list with a single element, because polylines is designed to draw multiple polygons at once
        cv2.polylines(copy_frame, [points_array], isClosed=False, color=(0,255,0), thickness = 2)

    cv2.imshow("Calibration", copy_frame)
    #the waitKey function here is used to pass keyboard data to the program, further down waitKey will have a different purpose
    #it also receives info about which keys were pressed, 0xFF is the mask because waitKey uses 32 bits
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        if len(point_list) < 3:
            print("Error: A polygon needs at least 3 points")
            continue
        with open(CONFIG_PATH, "w") as f:
            json.dump(point_list, f, indent=4)
        print(f"\n[SUCCESS] Zone was saved to '{CONFIG_PATH}':")
        print(point_list)
        break

    elif key == ord('c'):
        point_list.clear()
        print("Points have been cleared")

    elif key == ord('q'):
        print("Exiting without saving")
        break

cv2.destroyWindow("Calibration")
