import cv2
import json
import numpy as np
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
# aici pui cale absoluta catre un videoclip din calculator pe care vrei sa l analizezi
cap = cv2.VideoCapture(r"E:\cctv_lockers\data\clips\filmare_test_1.mp4")
if not cap.isOpened():
    print("Error: Could not open video source.")
    exit()

#ret reprezinta un nr in binar care arata daca a avut succes sau nu citirea
ret, first_frame = cap.read()
if not ret:
    print("Error reading frame.")
    cap.release()
    exit()

def mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        param.append((x,y))
    elif event == cv2.EVENT_RBUTTONDOWN:
        if len(param) > 0:
            param.pop()

#trebuie initializata lista inainte de a fi folosita
lista_puncte = []
cv2.namedWindow("Calibration")
cv2.setMouseCallback("Calibration", mouse, param=lista_puncte)


while True:
    #facem o copie pentru a nu pata frame urile originale
    copy_frame = first_frame.copy()
    for punct in lista_puncte:
        #punem cercuri unde apasam click ca sa avem un feedback
        #5 reprezinta raza cercului in pixeli
        #(0,0,255) reprezinta culoarea , in formatul BGR
        #-1 inseamna ca cercul este plin 
        cv2.circle(copy_frame, punct, 5, (0,0,255), -1)

    if len(lista_puncte) >= 2:
        #cv.polylines , functia care trage liniile are nevoie de np array
        #reshape(-1,1,2) => -1 reprezinta ca decide algoritmul cate linii are matricea, 1 adica cate coloane si 2 adica cate variabile : x , y
        puncte = np.array(lista_puncte, np.int32).reshape(-1, 1, 2)
        #isclosed = false pentru ca daca am desena al 3 lea punct, l ar uni cu primul si ar forma un triunghi. folosim true in varianta de productie cand avem coordonatele deja
        #[puncte] reprezinta o lista cu un singur element, deoarece polylines este conceputa sa deseneze mai multe poligoane simultan
        cv2.polylines(copy_frame, [puncte], isClosed=False, color=(0,255,0), thickness = 2)

    cv2.imshow("Calibrare", copy_frame)
    #functia waitkey aici are rolul de a trimite date de la tastatura catre program, mai jos waitkey va avea alta insemnatate
    #de asemenea, primeste info legat de tastele apasate, 0xFF este masca pentru ca waitkey foloseste 32 de biti . 
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        print("Saved points:", lista_puncte)
        break
    elif key == ord('q'):
        print("Exit without saving")
        break;

cv2.destroyWindow("Calibration")


while True:
    ret, frame = cap.read()
    if not ret:
        print("End of video or error reading frame.")
        break
    if len(lista_puncte) >= 2:
            puncte = np.array(lista_puncte, np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [puncte], isClosed=False, color=(0,255,0), thickness = 2)
    result = model.track(frame, persist = True, classes = [0], tracker = "bytetrack.yaml", verbose = False)
    result_frame = result[0].plot()
    cv2.imshow("Video", result_frame)
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()