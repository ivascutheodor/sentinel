# Sentinel

A general-purpose video surveillance system. Sentinel watches camera streams, detects people
entering a restricted zone, and stores an evidence clip of each presence interval. One
installation serves one organization of any kind (an office, a warehouse, a shop, a home or a
clinic).

| Part | Folder | Role |
|---|---|---|
| Worker | `workers/` | Reads a camera, stream or file, tracks people with YOLO, records H.264 clips and reports each event to the backend |
| Backend | `backend/` | FastAPI + PostgreSQL: accounts and sessions, events and clips, cameras, settings, video streaming |
| Frontend | `frontend/` | React dashboard: sign-in, event history, recording playback |

See `backend/README.md` and `frontend/README.md` for setup.
