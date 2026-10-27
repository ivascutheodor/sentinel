# Sentinel frontend

React, TypeScript, Tailwind CSS, and Vite. All changes for this integration are frontend-only.

```bash
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`. The root page is sign-in; authenticated views are `/dashboard`, `/events`, and `/settings`.

## Run against the current backend

The integration targets the authenticated application in **`backend/server/server.py` on `main`**. That application has the login, current-user, logout, events, and video routes used here. `backend/app/main.py` currently exposes a different application without the auth routes; the two entry points are not interchangeable.

`feat/frontend` has not yet incorporated the backend commits from `main`. No backend files were merged or edited during this integration. Run the up-to-date backend from a separate `main` checkout/worktree, or have its owner bring those changes into your branch before starting it. In that backend checkout, configure its `.env` from its current `.env.example`, including `WORKER_API_KEY`, then use its setup commands:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run fastapi dev server/server.py --host 0.0.0.0 --port 8000
```

PostgreSQL must already be running. The username migration on `main` must be applied. Create an actual account using the API branch's command if one does not exist:

```bash
uv run python -m server.create_user your_username "Your Name" --admin
```

The command prompts for a password; the account-creation tool requires at least 12 characters. The sign-in form does not impose a new password policy on existing accounts. There are no demo or hardcoded credentials.

Vite proxies `/api/v1` to `http://127.0.0.1:8000`. For a backend running elsewhere, copy `.env.example` to `.env.local`, change `SENTINEL_API_TARGET`, and restart Vite. No worker API key belongs in frontend configuration.

## Endpoint mapping

| Frontend action | Actual API call |
| --- | --- |
| Sign in | `POST /api/v1/auth/login` with `{ username, password }` |
| Account and session validation | `GET /api/v1/auth/me` |
| Log out | `POST /api/v1/auth/logout` (204 response) |
| Event history | `GET /api/v1/events` |
| Event details | `GET /api/v1/events/{event_id}` |
| Administrator's confirmed event deletion | `DELETE /api/v1/events/{event_id}` |
| Recording playback | `GET /api/v1/videos/{filename}` |

The backend returns `id`, `username`, `display_name`, and `role` for the current user. Usernames are canonical lowercase, 3–50 characters using letters, digits, dots, underscores, or hyphens. UI role labels map backend `admin`/`user` to Administrator/Operator. The session cookie stays HttpOnly; the frontend never stores passwords, session tokens, or worker keys. A 401 clears protected content and returns to sign-in.

The dashboard loads identity and event history separately instead of calling the nonexistent `/dashboard` endpoint. It polls every five seconds and cancels requests on navigation/unmount. Settings can show the actual account even if history is temporarily unavailable. The user icon opens Settings and Log out; Reduce animations is a browser-local preference.

## Event and recording contracts

`server/server.py` currently returns compact events: `{ id, camera_id, video_path, created_at }`. The frontend labels their timestamp **Registered**, keeps the actual camera UUID, and attempts playback through the existing filename-based video route. It does not claim that a returned path means the recording is ready, retained, or present on disk.

The adapter also accepts the rich event/clip response exposed by `app/main.py`: capture states, actual start/end times, clip ordering, readiness, failure, and expiry are preserved. Pending, failed, deleting, deleted, expired, or unsafe media paths are not offered for playback. This richer response support does not supply missing authentication routes to that application.

Recording URLs always remain same-origin. Only a URL-escaped filename is sent to `/videos/`; filesystem paths are never used as browser URLs or shown as event metadata. The served file must actually exist in the API's configured recordings root. A path alone does not establish that a recording is playable. Filenames in nested subdirectories cannot be served by the current single-filename route.

## Current backend limits

There is no camera-list/management API, live-view/snapshot API, or persisted event-review endpoint in these applications. The frontend does not call invented routes or create fake camera objects from event IDs. Camera configuration and review controls are omitted; event history still works without camera metadata. The live view explains its availability instead of falsely marking configured cameras offline. No mock cameras, sample media, synthetic alerts, or simulated review state are bundled.

The authenticated server currently authenticates event/media requests but does not filter event results by camera assignment or authorize video filenames against clip ownership. These are backend access-control requirements, not protections the frontend can enforce. The administrator-only delete button is a UI restriction; backend authorization remains the API's responsibility. Event deletion follows the actual backend behavior and does not delete video files. Changes to API authorization, worker ingestion, camera streaming, and the differing entry points require backend-owner work.

## Verification

- `pnpm test`: API contract, field mapping, lifecycle, URL/path containment, HTTP/cancellation, and malformed-response tests. Requires Node.js with TypeScript stripping (22.18+; Node.js 26 supported).
- `pnpm build`: TypeScript check and production bundle.
- `pnpm lint`: Oxlint.
- `pnpm preview`: serve the production build with the same API proxy.

For deployed static files, reverse-proxy `/api/v1` to the authenticated backend on the same origin and follow the backend's HTTPS cookie configuration.
