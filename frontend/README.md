# Sentinel dashboard

This dashboard uses the FastAPI API and PostgreSQL. It has no sample cameras, seeded alerts, static camera images, or preview accounts.

## First setup

1. Configure `backend/.env` using `backend/.env.example` and start PostgreSQL.
2. From `backend/`, run:

   ```bash
   docker compose up -d sentinel-db
   uv run alembic upgrade head
   uv run python -m app.create_admin
   uv run fastapi dev app/main.py --host 0.0.0.0
   ```

3. From this frontend folder:

   ```bash
   pnpm install
   pnpm dev
   ```

4. Open `http://localhost:5173`, sign in with the administrator you created, and select **Cameras → Add camera**. Enter the camera's RTSP address. Cameras are saved in PostgreSQL.

Vite proxies `/api/v1` to `http://127.0.0.1:8000`. To use another backend address, copy `.env.example` to `.env.local` and set `SENTINEL_API_TARGET`.

The API server requires **FFmpeg** to read camera frames. Camera views refresh a real snapshot after each request, with a three-second delay between requests; this is not a full-motion video stream. A failed request removes the image and shows the actual failure.

## Camera credentials

For password-protected cameras, put a named credential in the backend `.env`:

```dotenv
CAMERA_CREDENTIALS='{"front_door":{"username":"your-camera-user","password":"your-camera-password"}}'
```

Enter `front_door` in the camera's **Saved credentials name** field. Credentials and camera addresses are never returned to dashboard viewers.

## Detection and recordings

Live viewing and detection are separate. To detect people and create recordings, configure the existing worker using `workers/.env.example`:

- `SENTINEL_CAMERA_ID`: the UUID shown under the camera name on the Cameras page.
- `SENTINEL_VIDEO_SOURCE`: that camera's actual stream URL.
- `SENTINEL_WORKER_API_TOKEN`: the same secret as `WORKER_API_TOKEN` in the backend.
- `SENTINEL_CLIPS_DIR`: the same shared directory as backend `RECORDINGS_DIR` (the repository's `recordings/` directory by default).
- Configure the worker's detection polygon and detector model for the actual camera.

Run the worker with `python src/monitor.py` from `workers/` after installing `workers/requirements.txt`. FFmpeg with H.264 encoding is also required on the worker. Finished clips are encoded for browser playback and indexed through the authenticated worker API. Failed indexing requests remain as `.event.json` files beside the recording and retry on worker startup, every minute, and after another recording finishes.

The dashboard lists the latest 200 database events and plays available recordings. Review status is persisted per signed-in user in the audit log. No detection boxes, confidence scores, or threat classifications are fabricated. The worker reports its real inference heartbeat separately from camera-frame availability.

Disabling monitoring blocks further frame access; the worker stops when its next heartbeat is rejected. Enabling again requires restarting that worker. Ordinary users see only cameras assigned in `camera_access`; account and access-grant management UI is not implemented yet.

## Commands

- `pnpm dev`: start Vite.
- `pnpm build`: type-check and build to `dist/`.
- `pnpm preview`: preview the production build with the API proxy.

For deployed static files, route `/api/v1` to FastAPI on the same origin. Production sessions require HTTPS. Physical camera connectivity and detector accuracy must be checked with your actual installation.
