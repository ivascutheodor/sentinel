import cv2
import numpy as np

print("OpenCV version:", cv2.__version__)
cap = cv2.VideoCapture(r"E:\cctv_lockers\data\clips\filmare_test_1.mp4")
if not cap.isOpened():
    print("Error: Could not open video source.")
    exit()

ret, first_frame = cap.read()
if not ret:
    print("Error reading frame.")
    cap.release()
    exit()

def ascultator_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        param.append((x,y))
    elif event == cv2.EVENT_RBUTTONDOWN:
        if len(param) > 0:
            param.pop()

lista_puncte = []
cv2.namedWindow("Calibrare")
cv2.setMouseCallback("Calibrare", ascultator_mouse, param=lista_puncte)


while True:
    copy_frame = first_frame.copy()
    for punct in lista_puncte:
        cv2.circle(copy_frame, punct, 5, (0,0,255), -1)

    if len(lista_puncte) >= 2:
        puncte = np.array(lista_puncte, np.int32).reshape(-1, 1, 2)
        cv2.polylines(copy_frame, [puncte], isClosed=False, color=(0,255,0), thickness = 2)

    cv2.imshow("Calibrare", copy_frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        print("Puncte salvate:", lista_puncte)
        break
    elif key == ord('q'):
        print("Iesire fara sa salvez")
        break;



while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or error reading frame.")
        break
    if len(lista_puncte) >= 2:
            puncte = np.array(lista_puncte, np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [puncte], isClosed=False, color=(0,255,0), thickness = 2)
    cv2.imshow("Video", frame)
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()