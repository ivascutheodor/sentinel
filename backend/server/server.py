from datetime import datetime 
from fastapi import FastAPI, HTTPException, status 
#ce fac HTTPException si status
from pydantic import BaseModel, Field

app = FastAPI(title = "Sentinel backend API", version = "1.0.0")

fake_db: dict[int, dict] = {}
id_counter = 1

class EventCreate(BaseModel):
    camera_id: str
    video_path: str

class EventResponse(BaseModel):
    id: int
    camera_id: str
    video_path: str
    created_at: datetime

#TREBUIE FACUTA URMATOAREA MODIFICARE IN RECORDER.PY:
#În _start() nu mai pui niciun apel de rețea. Lași OpenCV să scrie cadrele pe disc în liniște.
#În _finish() pui singurul apel, declanșat doar când fișierul .mp4 este finalizat complet:

@app.post("/api/v1/events", response_model=EventResponse,
          status_code=status.HTTP_201_CREATED,
          tags=["Events"], summary="Saves a new indexed video"
          )
def create_event_db(event: EventCreate):
    global id_counter
    new_event = {
        "id": id_counter,
        "camera_id": event.camera_id,
        "video_path": event.video_path,
        "created_at": datetime.now(),
    }
    fake_db[id_counter] = new_event
    id_counter += 1
    return new_event

@app.get("/api/v1/events", response_model=list[EventResponse])
def get_all_events():
    return list(fake_db.values())

@app.get("/api/v1/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int):
    if event_id not in fake_db:
        raise HTTPException(status_code=404, detail="Event not found.")
    return fake_db[event_id]

@app.delete("/api/v1/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int):
    if event_id not in fake_db:
        raise HTTPException(status_code=404, detail="Event not found.")
    del fake_db[event_id]
    return None
