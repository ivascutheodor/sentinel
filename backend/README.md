# Sentinel Backend

Backend API for **Sentinel**, built with FastAPI.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Git
- Docker with Docker Compose for the local PostgreSQL database

## Setup

From the `backend/` directory:

```bash
uv sync
```

This installs the dependencies defined in `pyproject.toml` using the versions locked in `uv.lock`.

There is normally no need to manually activate `.venv`. Run project commands through:

```bash
uv run <command>
```

## Environment Configuration

Create the local environment file:

```bash
cp .env.example .env
```

Example:

```env
APP_NAME=Sentinel
DEBUG=True
ENVIRONMENT=development
API_PREFIX=/api/v1
WORKER_API_KEY=<long random string, same as the worker's SENTINEL_API_KEY>
```

The `.env` file must not be committed. Every variable without a default must be set,
or the app (and the tests) cannot start.

Whenever a new environment variable is introduced, update `.env.example` as well.

## Database Setup

Set a non-empty `POSTGRES_PASSWORD` in `.env`. The other database defaults in
`.env.example` connect the API to the local PostgreSQL container.

From the `backend/` directory, start PostgreSQL:

```bash
docker compose up -d sentinel-db
docker compose logs sentinel-db
```

Once the logs report that PostgreSQL is ready to accept connections, apply the
migration and check that the database matches the SQLAlchemy models:

```bash
uv run alembic upgrade head
uv run alembic check
```

## Database Foundation Scope

The initial migration creates the tables, PostgreSQL enum types, constraints, and
indexes represented by the SQLAlchemy models.

The `system_settings` table holds exactly one row (`id = 1`), the installation-wide
settings. A migration inserts it with the column defaults (retention 7 days, sessions
12 hours with a 30-minute idle timeout, ...), and triggers reject `DELETE` and
`TRUNCATE` on it. Admins change it with `PATCH /api/v1/settings` (audited, with old and
new values). The API reads it for:

- `retention_days`: the `expires_at` of each new clip. Changing it does not
  rewrite clips that already exist.
- `session_absolute_seconds`: the lifetime of a session, fixed at login.
- `session_idle_seconds`: the inactivity timeout, checked on every request, so a
  change also applies to sessions that are already open. The table requires it to
  be at most `session_absolute_seconds`.

`pre_roll_seconds`, `post_roll_seconds`, `clip_part_seconds` and
`confidence_threshold` are not used yet: the worker still reads its own `.env`.

The following database behavior remains follow-up work:

- Automatically advancing `updated_at` on updates.
- Rejecting `UPDATE`, `DELETE`, and `TRUNCATE` on audit logs.
- Enforcing event and clip lifecycle transitions, including terminal states.
- Preventing changes to an event's `config_snapshot`.

Comments in the schema and models that describe these protections express intended
behavior. The migrations do not implement those protections yet, and `alembic check`
does not verify them.

## Accounts and Login

Users log in with a username and password; the API answers with an `HttpOnly`
session cookie (`sentinel_session`). Only a SHA-256 hash of the session token is
stored. Passwords are hashed with Argon2.

Create an account (the password is prompted twice, at least 12 characters):

```bash
uv run python -m app.cli.create_user admin "Admin Name" --admin
```

The worker does not log in. It sends the shared secret from `WORKER_API_KEY` in an
`X-API-Key` header; its `SENTINEL_API_KEY` must have the same value.

## Run the API

```bash
uv run fastapi dev app/main.py --host 0.0.0.0
```

The API runs on port `8000` by default. Swagger documentation is at `/docs`, and the
health check at `/health`.

With `ENVIRONMENT=development`, startup creates the camera `test_camera_01` if it
does not exist, so the worker's default camera name works out of the box.

## Routes

All routes are under `API_PREFIX` (default `/api/v1`):

| Route | Who | Purpose |
|---|---|---|
| `POST /auth/login` | anyone | `{username, password}`; sets the session cookie; rate limited |
| `POST /auth/logout` | logged in | revokes the session |
| `GET /auth/me` | logged in | the current user |
| `POST /auth/password` | logged in | change your own password (`current_password`, `new_password`) |
| `POST /events` | worker (`X-API-Key`) | save a finished incident clip |
| `GET /events` | logged in | one page of events with their clips, newest first (see below) |
| `GET /events/{event_id}` | logged in | one event |
| `DELETE /events/{event_id}` | admin | delete the event's recordings (files), keep the record |
| `GET /videos/{filename}` | logged in | stream a `ready`, unexpired clip; audited |
| `GET /cameras` | logged in | cameras, without stream details |
| `GET /cameras/{id}` | admin | one camera with stream URL and zone |
| `POST /cameras`, `PATCH /cameras/{id}` | admin | create, edit, enable/disable a camera |
| `GET /users`, `POST /users`, `PATCH /users/{id}` | admin | list, create, change role/name/active |
| `POST /users/{id}/password` | admin | reset someone else's password |
| `GET /settings`, `PATCH /settings` | admin | read and change `system_settings` |

`401` means not logged in, `403` logged in without the admin role. Accounts get the admin
role from an admin, or from `create_user --admin` (the way to create the first one).

Everything that changes data or shows footage is written to `audit_logs`: logins (failed,
refused and successful), logouts, password changes, user, camera and settings changes,
deletions, and each time a clip is opened.

### Cameras

`PATCH` changes only the fields sent; `null` clears `location` or `credentials_ref`.
Cameras are disabled (`is_enabled: false`), never deleted: events point to them. Names are
unique ignoring case (the worker finds its camera by name); a taken name or stream URL is
a `409`. The zone is `detection_config.region`: a polygon of 3 to 16 `[x, y]` pixel points,
or `null` for none. Stream URLs must be `rtsp://host[:port]/path` without a user or password
(`credentials_ref` names where the credentials are kept instead).

### Users

Accounts are deactivated, never deleted. Passwords are 12 to 1024 characters. A role change,
a deactivation or an admin password reset logs that user out everywhere; changing your own
password logs out your other sessions and keeps the current one. An admin cannot remove
their own admin role or deactivate themselves, and the last active admin cannot be
removed, so the system always keeps one.

### Login rate limiting

Failed logins are counted from `audit_logs` over the last 15 minutes. After 5 failures
for one username (whether or not it exists) or 20 from one IP address, the login answers
`429` with a `Retry-After` header (seconds), even for the right password. Refused attempts
are audited as `session.login_throttled` and don't extend the block. Someone guessing a
username can lock that person out for 15 minutes; the per-IP limit keeps that contained.

### Deleting recordings

`DELETE /events/{id}` (admin) removes each clip's video and manifest from `recordings/`.
Each clip goes `deleting` (committed first), then `deleted` once its files are gone. The
event and clip rows stay, so the event is still listed, as "recording deleted". If a file
can't be removed (on Windows, for example, while it is being streamed), the clip stays
`deleting` and the answer is `409`; deleting again retries.

### Watching clips

`GET /videos/{filename}` serves only files that belong to a clip that is `ready` and not
past `expires_at`; anything else is `404`. Opening a clip writes one `clip.view` audit row;
the browser's follow-up `Range` requests don't add more.

## Events and Video Clips

The worker posts one event when a clip is finished. Only `camera_id` (the camera's
**name**) and `video_path` (a plain file name inside `recordings/`, no folders) are required:

```json
{
  "camera_id": "test_camera_01",
  "video_path": "incident_2026-10-08_10-00-00.mp4",
  "started_at": "2026-10-08T10:00:00Z",
  "last_person_seen_at": "2026-10-08T10:00:20Z",
  "closed_at": "2026-10-08T10:00:25Z",
  "end_reason": "person_absent",
  "recorded_start_at": "2026-10-08T09:59:55Z",
  "recorded_end_at": "2026-10-08T10:00:25Z",
  "size_bytes": 1048576,
  "config_snapshot": {
    "schema_version": 1,
    "model_ref": "yolo11n.pt",
    "detection_config": { "schema_version": 1, "region": null },
    "settings": { "pre_roll_seconds": 5, "post_roll_seconds": 5 }
  },
  "source_manifest_ref": "manifests/incident_2026-10-08_10-00-00.json"
}
```

The backend decides the rest:

- `end_reason` `person_absent` (the default) gives a `completed` event; any other
  reason listed in `/docs` gives an `interrupted` one.
- The clip is `ready` when `size_bytes` and the recorded start/end are sent,
  otherwise `pending`.
- `expires_at` is `system_settings.retention_days` after saving.
- Missing times fall back to "now"; a missing snapshot falls back to a default one.

### Manifests

For every clip the worker writes a manifest, `recordings/manifests/<clip name>.json`,
before posting the event: the camera, the times, the config snapshot, and the video's
size and SHA-256. It carries `"synced": false` until the backend has stored the event.

When the request names a manifest (`source_manifest_ref`, always
`manifests/<plain name>.json`), the backend verifies it before saving anything: the
manifest must exist, name the same camera and file, and the clip on disk must have the
same size and SHA-256. Any mismatch is a `422`, so a clip changed after recording is
never stored as evidence. A verified clip keeps the manifest reference and its
`sha256`. Without a manifest, the clip gets a `placeholder/<uuid>` reference and no hash.

Posting the same clip twice returns `409`; the worker's `sync_manifests.py` treats that
as "already stored" when it re-sends events that failed while the backend was down.

Times must include a timezone. The three event times are sent together or not at
all, and must be in order; the two recorded times likewise, with end after start.
Unknown fields, unknown cameras and events, and bad input are rejected with `422`
or `404`; database conflicts (for example the same clip file posted twice) return
`409`.

### Listing events

`GET /events` returns one page, newest `started_at` first:

```json
{ "items": [ { "id": "...", "camera_name": "test_camera_01", "clips": [ ... ] } ],
  "total": 412, "limit": 50, "offset": 100 }
```

`total` counts every event that matches the filters, not only the ones in `items`.
Query parameters, all optional:

| Parameter | Default | Meaning |
|---|---|---|
| `limit` | `50` | events per page, 1 to 200 |
| `offset` | `0` | events to skip: page `n` (from 0) is `offset = n * limit` |
| `camera_id` | | only this camera (its UUID) |
| `started_from` | | `started_at >= started_from` (inclusive) |
| `started_to` | | `started_at < started_to` (exclusive) |

Times need a timezone. In a URL, `+` means a space, so send UTC with `Z`
(`2026-10-08T10:00:00Z`) or encode `+` as `%2B`. Out-of-range values, a missing
timezone, or `started_from >= started_to` return `422`.

Every event also has `camera_name` next to `camera_id`.

## Tests

Run all tests:

```bash
uv run pytest
```

Run a specific test file:

```bash
uv run pytest tests/test_health.py
```

Run tests with verbose output:

```bash
uv run pytest -v
```

PostgreSQL integration tests run when `TEST_DATABASE_URL` points to a database
with the existing migrations applied:

```bash
TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/TEST_DB' uv run pytest
```

In PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/TEST_DB"
uv run pytest
```

Use a test database. Each integration test rolls back its outer transaction;
request-level commits use savepoints so test cameras, events, and clips are not
retained. Without this variable, database integration tests are skipped and
request validation, health, and video-serving tests still run.

## Linting

Check the code with Ruff:

```bash
uv run ruff check .
```

Automatically fix supported issues:

```bash
uv run ruff check . --fix
```

## Formatting

Format the code:

```bash
uv run ruff format .
```

Check formatting without modifying files:

```bash
uv run ruff format . --check
```

## Before Committing

Run:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

All checks should pass before merging changes into `main`.

## Dependencies

Add a runtime dependency:

```bash
uv add <package>
```

Add a development dependency:

```bash
uv add --dev <package>
```
