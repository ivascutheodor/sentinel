# Sentinel — Project Context for Claude Code

> Verified state: 2026-10-28, branch `feat/system-settings-seed` (uncommitted) on top of
> `origin/main` @ `e80169f` (PR #6: one backend app). It seeds `system_settings` (4.6).
> This file is the single source of truth for an agent joining the repo: what the project is,
> what works, what is broken, what comes next. Read it before changing code, and update it when
> any of that changes.

---

## 1. What Sentinel is

A **single-clinic video surveillance system**: it detects people entering a restricted zone and
stores an evidence clip of each presence interval.

| Part | Folder | Tech | Role |
|---|---|---|---|
| Worker | `workers/` | Python 3.12, Ultralytics YOLO, OpenCV, imageio-ffmpeg, `requests` | Reads a camera/stream/file, tracks people, checks whether a person's foot point is inside a polygon, records an H.264 clip with pre-roll/post-roll, then posts the event to the backend |
| Backend | `backend/` | Python ≥3.13 (venv is 3.14), FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 18, argon2-cffi | Auth, persists events and clips, serves the API and the video bytes |
| Frontend | `frontend/` | React 19 + TypeScript + Vite + Tailwind | Built by a colleague on `origin/feat/frontend` (see 6); `main` still has the Vite scaffold |

```
camera/stream --YOLO track--> foot point in polygon? --yes--> IncidentRecorder (pre-roll buffer)
  -> FfmpegWriter writes H.264 clip -> Incident -> monitor.report_incident()
  -> POST /api/v1/events (X-API-Key) -> PostgreSQL (events + video_clips)
  -> browser (session cookie) -> GET /api/v1/events, GET /api/v1/videos/{filename}
```

Two people work on it: the user (backend + worker, learning; explain changes, **do not commit or
push unless asked**) and a colleague (frontend; also committed backend code, see 4.1).

---

## 2. Git state

| Branch | State |
|---|---|
| `origin/main` @ `e80169f` | PRs #4 (auth), #5 (real event data), #6 (one backend app + this file) |
| `feat/system-settings-seed` (local, **uncommitted**) | Seeds `system_settings`, reads retention and session timeouts from it. 47 tests pass + 1 Windows skip (with the DB) |
| `origin/feat/frontend` | Colleague's frontend, 9+ commits ahead of `main`, not merged. Also commits `.pnpm-store/` (should be git-ignored) |
| local `refactor/single-backend-app`, `feat/real-event-data`, `fix/worker-api-contract`; remote `refactor/single-backend-app` | Fully merged; safe to delete (`git branch -d`, `git push origin --delete`) |

Check whether a branch is merged without merging it: `git fetch --prune`, then
`git log --oneline origin/main..<branch>` (empty = nothing to lose) or
`git branch -a --merged origin/main`.

Untracked: `CLAUDE.md` (this file, not committed yet). Commit style: Conventional Commits
(`feat(worker): ...`, `fix: ...`, `refactor: ...`).

---

## 3. Repository layout (as on `origin/main`)

```
sentinel/
├── CLAUDE.md
├── README.md                    <- one line
├── recordings/                  <- clip storage: the worker writes here, the backend serves from here
│                                   (test1.mp4 = H.264 test input video; *.mp4 is git-ignored)
├── backend/
│   ├── .env / .env.example      <- .env is git-ignored; .env.example must keep WORKER_API_KEY empty
│   ├── alembic.ini, compose.yaml, pyproject.toml, uv.lock, README.md
│   ├── app/
│   │   ├── main.py              <- THE FastAPI app: lifespan (dev camera seed), CORS, routers, /health
│   │   ├── api/deps.py          <- SessionDep, get_current_session/user, verify_worker_key, session timings
│   │   ├── api/auth.py          <- /auth/login, /auth/logout, /auth/me
│   │   ├── api/events.py        <- /events (worker POST, logged-in GET/DELETE)
│   │   ├── api/videos.py        <- /videos/{filename} (logged in)
│   │   ├── schemas/auth.py      <- LoginRequest, UserResponse
│   │   ├── schemas/events.py    <- ConfigSnapshot, EventCreate (worker contract), EventResponse
│   │   ├── services/audit.py    <- audit() helper for audit_logs rows
│   │   ├── cli/create_user.py   <- CLI to create accounts
│   │   ├── core/config.py       <- pydantic-settings, env_file=".env" (relative to CWD!)
│   │   ├── core/security.py     <- Argon2 password hashing, session token + SHA-256 hash
│   │   ├── core/version.py
│   │   ├── db/session.py        <- engine, SessionFactory, get_session()
│   │   ├── db/enums.py          <- StrEnum + native PG enums
│   │   ├── db/models/           <- 9 ORM models, one file each
│   │   ├── db/schema.sql        <- design DDL; intent in comments; OUT OF DATE vs migrations
│   │   └── .env                 <- empty leftover, delete
│   ├── migrations/versions/     <- 2feed91c7392 (initial), ea5ce070565b (users.email -> username),
│   │                               b7c1d9e4f2a6 (seed system_settings + no-delete triggers) = head
│   ├── src/                     <- stray yolo*.pt copies, unused (git-ignored)
│   └── tests/                   <- conftest (ENVIRONMENT=test), test_health, test_auth, test_security,
│                                   test_event_create, test_videos, test_events (DB, needs TEST_DATABASE_URL)
├── workers/
│   ├── .env                     <- git-ignored; contains only SENTINEL_API_KEY
│   ├── .env.example             <- WRONG values, see 5.4
│   ├── requirements.txt         <- UTF-8, pinned, complete
│   ├── src/config.py            <- frozen dataclass from os.getenv + workers/.env
│   ├── src/monitor.py           <- entrypoint: YOLO loop, FfmpegWriter, config snapshot, HTTP post
│   ├── src/recorder.py          <- IncidentRecorder state machine -> Incident
│   ├── src/zone.py, zone_selector.py, config_zona.json
│   └── tests/test_recorder.py
└── frontend/                    <- Vite scaffold on main
```

---

## 4. Backend

### 4.1 One app: `app/main.py`

History: `app/main.py` was deleted in the auth work, then re-created by the colleague in
`5851cf9` (routers + schemas, no auth, a client-built `clips` contract) while `server/server.py`
kept running. Branch `refactor/single-backend-app` merged them: the colleague's structure, with
`server.py`'s auth, worker key and worker contract moved in; `server/` is deleted. Decisions:

- `POST /events` uses the **worker** contract (4.4): the backend decides event/clip status,
  `expires_at` and the manifest, not the client. `extra="forbid"`: unknown fields are a 422.
- Responses use the colleague's richer `EventResponse` (with `clips[]`); the frontend parses it.
- `DELETE /events/{id}` removes the clip rows first (the colleague's version returned 409 for any
  event with a clip, which would have broken the frontend's delete button).
- DB conflicts on create are a 409 (from the colleague's version).
- `on_event` replaced by `lifespan`; the `test_camera_01` seed runs only when
  `ENVIRONMENT=development`; CORS origins from `CORS_ORIGINS` (JSON list, default
  `["http://localhost:5173"]`).

```bash
uv run fastapi dev app/main.py --host 0.0.0.0     # docs at http://127.0.0.1:8000/docs
```

### 4.2 Routes (all under `API_PREFIX`, default `/api/v1`)

| Route | Auth | Notes |
|---|---|---|
| `GET /health` (no prefix) | none | |
| `POST /auth/login` | none | body `{username, password}`; sets `sentinel_session` HttpOnly cookie (SameSite=Lax); writes `audit_logs` (success/denied) |
| `POST /auth/logout` | cookie | revokes the session, 204 |
| `GET /auth/me` | cookie | `{id, username, display_name, role}` |
| `POST /events` | `X-API-Key` = `WORKER_API_KEY` | worker only; see 4.4; 404 unknown camera, 409 conflict |
| `GET /events` | cookie | all events with clips, newest first; **no pagination/filters** |
| `GET /events/{id}` | cookie | |
| `DELETE /events/{id}` | cookie (any role) | deletes clip rows + event; does **not** delete the file |
| `GET /videos/{filename}` | cookie | bare file name only (no `/`, `\`, NUL), symlink guard, `inline`; serves any file in `recordings/` (not checked against the DB) |

### 4.3 Auth design

- Passwords: Argon2 (`argon2-cffi` `PasswordHasher`), rehash on login when parameters change;
  unknown usernames still run a dummy verify. No rate limiting.
- Sessions: opaque `secrets.token_urlsafe(32)` in the cookie; only its SHA-256 digest is stored
  (`user_sessions.token_hash`, 32 bytes). Absolute lifetime 12 h, idle timeout 30 min
  (`system_settings.session_absolute_seconds` applied at login, `session_idle_seconds` checked
  on every request, so changing it affects open sessions).
  `last_seen_at` is written at most once per 60 s.
- `get_current_user` rejects revoked/expired/idle sessions and inactive users. Roles exist
  (`admin`, `user`) but **no endpoint checks the role yet**.
- Worker: shared secret, `secrets.compare_digest` on `X-API-Key`.
- Usernames: `^[a-z0-9._-]{3,50}$` (DB CHECK), lower-cased on login.
- Create accounts (password ≥ 12 chars, prompted twice, input hidden):
  `uv run python -m app.cli.create_user admin "Admin Name" --admin`

### 4.4 `POST /events` contract (what the worker sends)

`EventCreate` in `app/schemas/events.py` (only `camera_id` + `video_path` required, so old
workers still work; unknown fields → 422):

| Field | Type | Notes |
|---|---|---|
| `camera_id` | str | camera **name** (`test_camera_01`), not UUID; unknown → 404 |
| `video_path` | str | file **name** only, inside `recordings/` |
| `started_at`, `last_person_seen_at`, `closed_at` | aware datetime | all three or none; must be ordered; missing → backend uses "now" |
| `end_reason` | literal | default `person_absent` → `completed`; anything else (`stream_lost`, `manual_stop`, ...) → `interrupted` |
| `recorded_start_at`, `recorded_end_at` | aware datetime | both or neither; end > start |
| `size_bytes` | int > 0 | |
| `config_snapshot` | `ConfigSnapshot` | `{schema_version: 1, model_ref, detection_config, settings}`; missing → `DEFAULT_CONFIG_SNAPSHOT` (fake, `region: null`) |

Validation mirrors the DB CHECKs so bad input is a **422 with a message**, not a 500. The clip
is `ready` (with `source_ready_at = now`) when `size_bytes` and the recorded span are sent,
otherwise `pending`.

`EventResponse`: `id, camera_id (UUID), event_type, status, started_at, last_person_seen_at,
closed_at, end_reason, created_at, config_snapshot, clips[]`; each clip (`VideoClipResponse`)
has every `video_clips` column (`filepath`, `status`, `size_bytes`, `expires_at`, ...).
No `duration_seconds` and no camera name: the client computes the duration.

`expires_at = now + system_settings.retention_days` (read at save time; existing clips are not
rewritten when it changes). Still fake: `source_manifest_ref = manifests/<uuid>.json` (never
written).

### 4.5 Settings and `.env`

`app/core/config.py`, `env_file=".env"` relative to the **current directory** → always run from
`backend/`. Required: `APP_NAME`, `ENVIRONMENT` (`development|production|test`), `API_PREFIX`,
`POSTGRES_DB/HOST/USER/PORT/PASSWORD`, `WORKER_API_KEY`. Optional: `DEBUG`,
`SESSION_COOKIE_NAME` (`sentinel_session`), `SESSION_COOKIE_SECURE` (False; True on HTTPS),
`CORS_ORIGINS` (JSON list). A missing required value makes **every import fail, including
pytest**. `tests/conftest.py` forces `ENVIRONMENT=test` so tests skip the camera seed and don't
need a DB; set `TEST_DATABASE_URL` to run the PostgreSQL tests (each runs in a rolled-back
transaction, so the dev DB is safe), otherwise they are skipped.

`backend/.env` is read by Docker Compose (variable substitution) and by pydantic-settings.
Keep values unquoted. Update `.env.example` (with empty secrets) whenever a variable is added.

### 4.6 Database

- `postgresql+psycopg`, `pool_pre_ping=True`. `migrations/env.py` uses `app.db.session.engine`.
- Docker: service `sentinel-db`, `postgres:18`, container `backend-sentinel-db-1`, port 5432,
  volume `postgres_data`. `docker compose down -v` **deletes the database**.
- Head: `b7c1d9e4f2a6`. Errors such as `column users.username does not exist` or
  `system_settings row is missing` mean a migration was not applied: `uv run alembic upgrade head`.
- Tables: `cameras`, `events`, `video_clips`, `media_jobs` (unused), `system_settings`,
  `users`, `user_sessions`, `camera_access` (unused), `audit_logs`, `alembic_version`.
- `system_settings`: exactly one row (`id = 1`), seeded by `b7c1d9e4f2a6` with the column
  defaults (retention 7 d, pre/post roll 10 s, parts 60 s, confidence 0.60, session 43200 s,
  idle 1800 s). Triggers reject `DELETE`/`TRUNCATE`; change it with `UPDATE`. Read through
  `app/services/system_settings.get_system_settings(session)`. Used: `retention_days`,
  `session_absolute_seconds`, `session_idle_seconds`. Not used yet: pre/post roll, clip parts,
  confidence (the worker reads its own `.env`; see item 14 in section 8).

### 4.7 Constraints that will bite you

Violations raise `CheckViolation`/`NotNullViolation`/`IntegrityError` at flush: `POST /events`
turns them into 409, other routes into 500.

- `cameras.stream_url`: NOT NULL, UNIQUE, must match `^rtsp://...`. `detection_config`: exactly
  `schema_version` (=1) and `region` (null or polygon, `match_rule="bottom_center"`, 3–16 points).
- `events`: `last_person_seen_at >= started_at`, `closed_at >= last_person_seen_at`;
  `capturing` ⇒ no `closed_at`/`end_reason`; `completed` ⇒ `person_absent`; `interrupted` ⇒ one of
  `stream_lost|worker_restart|manual_stop|camera_disabled|inference_stalled|recording_failed`;
  `config_snapshot` must have the 4 keys; one `capturing` event per camera (partial unique index).
- `video_clips`: `ready` requires `filepath`, `size_bytes > 0`, `recorded_start_at`,
  `recorded_end_at` (> start), `source_ready_at`; `deleting|deleted` need `delete_requested_at`;
  `failed` needs `failure_code`; `filepath` and `(event_id, part_number)` unique;
  `ON DELETE NO ACTION` from events (delete clips first).
- `user_sessions.token_hash`: 32 bytes; `expires_at > created_at`, `last_seen_at >= created_at`.
- `system_settings`: `id = 1`; `session_idle_seconds <= session_absolute_seconds` (lower both
  together); retention and part length > 0; confidence in [0, 1].

`schema.sql` describes protections **not implemented** in any migration: `updated_at` trigger,
immutable `audit_logs`, clip/event transition triggers, immutable `config_snapshot`.

### 4.8 Backend commands

```bash
cd backend
uv sync
docker compose up -d sentinel-db
uv run alembic upgrade head
uv run alembic check                 # "No new upgrade operations detected."
uv run fastapi dev app/main.py --host 0.0.0.0     # docs at http://127.0.0.1:8000/docs
uv run pytest                        # DB tests skip unless TEST_DATABASE_URL is set
uv run ruff format . && uv run ruff check .
```

```powershell
# PostgreSQL tests from PowerShell (password from backend\.env)
$env:TEST_DATABASE_URL = "postgresql+psycopg://sentinel:<password>@127.0.0.1:5432/sentinel"
uv run pytest
```

---

## 5. Worker (`workers/`)

### 5.1 Pipeline

1. `load_zone()` → polygon from local `config_zona.json` (4 points). `cameras.detection_config`
   and `stream_url` in the DB are **not used** by the worker.
2. `model.track(frame, persist=True, classes=[0])` → people with track IDs.
3. `foot_point(box)` = bottom-centre; `is_in_zone` = `cv2.pointPolygonTest(...) >= 0`.
4. `recorder.update(raw_frame, someone_in_zone)` per frame (`raw_frame` has no overlays).
5. `IncidentRecorder` (`recorder.py`, no YOLO/OpenCV/HTTP so it is unit-testable): keeps
   `(time, frame)` pairs for pre-roll (buffer ≥ 1), needs `min_presence_frames` in a row to
   start, writes post-roll after the zone empties, then returns an **`Incident`** dataclass:
   `clip, started_at` (first frame of the presence streak), `last_person_seen_at`, `closed_at`,
   `end_reason`, `recorded_start_at`, `recorded_end_at`. Times come from an injectable `clock`
   (UTC); for video files they are processing times, for a live camera real times.
6. `monitor.report_incident()` posts the incident with the file size and the config snapshot
   built once by `build_config_snapshot()`. Logs status and body on HTTP errors. **No retry**.
7. On exit `recorder.close(end_reason)`: `stream_lost` when the video ends, `manual_stop` on `q`.
   The worker **exits** when the stream ends; no reconnect.

### 5.2 Video writing

`FfmpegWriter` in `monitor.py` pipes BGR frames into the FFmpeg bundled with `imageio-ffmpeg`:
`libx264`, `yuv420p`, `-preset veryfast`, `-movflags +faststart`. Works on Windows/macOS/Linux and
plays in every browser (verified: h264, ~40 dB PSNR vs source). Do **not** go back to
`cv2.VideoWriter`: `mp4v` does not play in Chrome/Firefox, and OpenCV's `avc1` needs an OpenH264
DLL that is not installed (it only worked via a Windows-only fallback, with `[ERROR]` noise).

### 5.3 Configuration (`src/config.py`)

| Env var | Default |
|---|---|
| `SENTINEL_VIDEO_SOURCE` | `recordings/test1.mp4` (repo root) |
| `SENTINEL_ZONE_CONFIG` | `workers/src/config_zona.json` |
| `SENTINEL_MODEL` | `workers/yolo11n.pt` |
| `SENTINEL_CLIPS_DIR` | `../recordings` → `E:\sentinel\recordings` (what the backend serves) |
| `SENTINEL_API_URL` | `http://127.0.0.1:8000/api/v1` |
| `SENTINEL_CAMERA_ID` | `test_camera_01` (camera **name**) |
| `SENTINEL_API_KEY` | `""` → must equal backend `WORKER_API_KEY`, else 401 |
| `SENTINEL_PRE_ROLL_SECONDS` / `POST_ROLL` / `MIN_PRESENCE_SECONDS` | `5` / `5` / `2` |
| `SENTINEL_SHOW_WINDOW` / `SENTINEL_DEBUG` | `1` / `0` |

Relative paths resolve against `workers/`. `os.getenv` does not strip quotes: keep values unquoted.

### 5.4 Gotchas

- `workers/.env.example` is wrong: quoted values, `SENTINEL_CLIPS_DIR=sentinel/recordings`, a
  non-existent video source. **Do not copy it**; the defaults are correct.
- Clip names are `incident_<local time to the second>.mp4`: no camera name, can collide.
- The worker uses `E:\sentinel\.venv` (Python 3.12, pip), not uv. pytest is not installed there;
  the recorder tests only need the standard library. `workers/` has no ruff config.

### 5.5 Worker commands (PowerShell)

```powershell
E:\sentinel\.venv\Scripts\Activate.ps1
pip install -r E:\sentinel\workers\requirements.txt
cd E:\sentinel\workers\src
$env:SENTINEL_MIN_PRESENCE_SECONDS="0.5"   # easier to trigger with test1.mp4
python monitor.py                           # 'q' quit, 'p' pause
python zone_selector.py                     # draw the polygon, 's' saves
cd E:\sentinel\workers; pytest tests        # after: pip install pytest
```

---

## 6. Frontend (`origin/feat/frontend`, colleague)

Out of scope for the user; record only what the backend must satisfy. Login page + dashboard
(events panel, event detail, recording player), Dockerfile + `frontend/compose.yaml`.
`src/lib/api.ts` fetches `/api/v1/...` through a Vite proxy (`SENTINEL_API_TARGET`, default
`http://127.0.0.1:8000`) or a build-time `VITE_API_ORIGIN`.

It calls only routes that exist in `app/main.py`:
`POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, `GET /events`, `GET /events/{id}`,
`DELETE /events/{id}`, `GET /videos/{filename}`. `src/lib/backend.ts` parses **both** event
shapes: the old flat server.py one (`video_path`, `clip_status`) and the current one
(`clips[]` with `filepath`, `status`, `expires_at`). The earlier mismatches
(`/session`, `/dashboard`, `/cameras`, `/events/{id}/review`, email/roles) were dropped on the
frontend side; camera endpoints and roles will be needed again later.

---

## 7. Verified (Windows, PowerShell)

On 2026-10-26:

- Docker DB up, migrations at head, `alembic check` clean, 16 backend + 4 recorder tests pass.
- Admin created with `create_user`; via `/docs`: unauthenticated 401, wrong password 401 +
  `denied` audit row, login 200 + cookie, `/auth/me` 200, logout 204 then 401.
- `POST /events`: no key 401; old 2-field body → `pending`, 0 s; full body → `ready`, real
  duration; bad order → 422; `stream_lost` → `interrupted`.
- Worker on `test1.mp4`: events saved `ready` with real sizes/durations; `completed/person_absent`
  and `interrupted/manual_stop` observed; clip played in the browser.

On 2026-10-27, after merging the apps (`refactor/single-backend-app`):

- `uv run pytest` with `TEST_DATABASE_URL`: 41 passed, 1 skipped (symlink test needs admin
  rights on Windows). Without the DB: 34 passed, 8 skipped. Ruff clean.
- `fastapi run app/main.py` smoke test: `/auth/me` anonymous 401, login 200 + cookie, worker
  POST without key 401 and with key 201 (`completed`, clip `ready`), list 200, video 200
  (`video/mp4`) and anonymous 401, logout 204. Test rows removed afterwards.
- One older event (2026-10-26 18:27) has no clip row; left as is.

On 2026-10-28, `feat/system-settings-seed`:

- Migration `b7c1d9e4f2a6`: upgrade → 1 row + 2 triggers; downgrade → 0 + 0; upgrade again →
  1 + 2. `alembic check` clean. Manual `DELETE` and `TRUNCATE` both rejected.
- `uv run pytest` with the DB: 47 passed, 1 skipped; without: 34 passed, 14 skipped. Ruff clean.
  New `tests/test_system_settings.py` (seeded defaults, removal blocked, login lifetime and idle
  timeout follow the row) and a retention test in `test_events.py`. The DB fixtures
  (`db_connection`, `db_app`) moved to `tests/conftest.py`. The row kept its defaults afterwards.

---

## 8. What is left (prioritised; frontend UI excluded)

**🔴 Do first**
1. ~~Merge the two apps~~ — done, PR #6 merged.
2. ~~Run all tests including the DB ones~~ — done (section 7).
3. Keep this file in sync after each step.

**🟠 APIs the frontend needs**
4. `GET /events`: `limit`/`offset` + `total`, filters by camera and date range, camera name,
   newest first.
5. Cameras: `GET /cameras` for everyone; create/edit/disable for admins.
6. `require_admin` dependency; use it.
7. `DELETE /events/{id}`: admin-only, delete the file too (`deleting` → `deleted`); consider
   keeping the event row as metadata.
8. Admin user management (list/create/role/deactivate/reset password) + change own password,
   all audited; replaces `create_user`.
9. Video endpoint: serve only files of a `ready`, unexpired clip in the DB; audit who watched what.
10. Login rate limiting (the frontend already handles 429).
11. Ask the colleague: "mark event as reviewed"?

**🟡 Data still fake**
12. ~~Migration seeding `system_settings`; read retention and session timeouts from it~~ — done
    on `feat/system-settings-seed` (4.6). No API to change the settings yet (admin endpoint,
    audited, later).
13. `source_manifest_ref`: real manifest or documented placeholder.
14. Unique clip names (camera name + milliseconds or UUID).

**🟡 Worker for real use**
15. Retry / local queue for failed posts.
16. Reconnect on stream loss instead of exiting.
17. Load stream URL and zone from the camera's DB row instead of local files (multi-camera).
18. Orphan check: files without events, events without files.

**🟡 Retention and database**
19. Retention cleanup job: delete files past `expires_at`, mark clips `deleted` (privacy).
20. Migration for the `schema.sql` triggers; then delete or regenerate `schema.sql`.
21. Endpoint tests against the real DB (auth, events, videos, permissions).

**⚪ Housekeeping**
22. Fix `workers/.env.example`.
23. Delete `backend/app/.env`, `backend/src/`, merged local branches.
24. Worker dev setup: `requirements-dev.txt` with pytest, ruff config for `workers/`.
25. Real top-level `README.md` (start DB, backend, worker).

**⚪ Before real use in the clinic**
26. Test with an RTSP stream (MediaMTX re-streaming `test1.mp4`); no camera is available.
27. HTTPS + `SESSION_COOKIE_SECURE=True`, real CORS origin or reverse proxy.
28. Deployment: Docker for backend and worker.
29. Database backups, and a backup plan for the video files.
30. Logging instead of `print`.

---

## 9. Conventions and gotchas

- Backend: always `uv run …` from `backend/`. uv warns that `VIRTUAL_ENV=E:\sentinel\.venv` does
  not match and uses `backend/.venv` — that is correct.
- Worker: run from `workers/src/` (flat imports) with `E:\sentinel\.venv` active.
- Ruff: line length 100, rules `E, F, I, UP, B`; run before committing.
- 422 = request body failed Pydantic validation before the handler ran. 500 is usually a CHECK
  constraint (4.7). 401 on worker posts = API key mismatch.
- Never commit `.env`, real secrets in `.env.example`, `*.mp4`, `*.pt`.
- After any model change: `alembic check` and a new migration (nothing is applied automatically).
- The backend must run on the machine that holds `recordings/`.
