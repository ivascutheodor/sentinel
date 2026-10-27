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
```

The `.env` file must not be committed.

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
indexes represented by the SQLAlchemy models. The following database behavior
remains follow-up work:

- Automatically advancing `updated_at` on updates.
- Rejecting `UPDATE`, `DELETE`, and `TRUNCATE` on audit logs.
- Enforcing event and clip lifecycle transitions, including terminal states.
- Preventing changes to an event's `config_snapshot`.
- Seeding the `system_settings` singleton and preventing its removal. Currently,
  its primary key and check constraint allow at most one row; a fresh database
  contains no settings row.

Comments in the schema and models that describe these protections express intended
behavior. The current migration does not implement those protections, and
`alembic check` does not verify them.

## Run the API

```bash
uv run fastapi dev server/server.py --host 0.0.0.0
```

The original entry point also serves the same application:

```bash
uv run fastapi dev server/server.py --host 0.0.0.0
```

The API runs on port `8000` by default.

Swagger documentation is available at:

```text
/docs
```

The current health endpoint is:

```text
/health
```

## Events and Video Clips

The event routes use the existing PostgreSQL connection in `app/db/session.py`
and the `POSTGRES_*` settings in `.env`. Event data persists across API restarts.
Both entry points expose the same routes under `API_PREFIX` (default `/api/v1`):

- `POST /api/v1/events`: create an event and optional video clips atomically.
- `GET /api/v1/events`: list events, including their clips, newest first.
- `GET /api/v1/events/{event_id}`: retrieve an event by UUID.
- `DELETE /api/v1/events/{event_id}`: delete an event without related clips.
- `GET /api/v1/videos/{filename}`: serve a file from `sentinel/recordings/`.

`camera_id` must be the UUID of an existing row in `cameras`. Register the camera
in PostgreSQL before sending events; there is not yet a camera management API.
Unknown cameras or events return `404`, invalid requests return `422`, and
database constraint conflicts return `409`. Deleting an event with related clips
returns `409`; this endpoint does not delete video files or cascade into clips.

For local development, register a camera using your actual name and RTSP address
(without embedded credentials), then use the returned UUID in event requests:

```sql
INSERT INTO cameras (name, stream_url)
VALUES ('Entrance', 'rtsp://camera-host/stream')
RETURNING id;
```

The old `{ "camera_id": "test_camera_01", "video_path": "..." }` request is replaced
by the database contract. Send actual timezone-aware recording timestamps and the
configuration used when the event started. For example, a completed recording:

```json
{
  "camera_id": "00000000-0000-0000-0000-000000000001",
  "status": "completed",
  "started_at": "2026-10-08T10:00:00Z",
  "last_person_seen_at": "2026-10-08T10:00:20Z",
  "closed_at": "2026-10-08T10:00:30Z",
  "end_reason": "person_absent",
  "config_snapshot": {
    "schema_version": 1,
    "model_ref": "yolo11n.pt",
    "detection_config": { "schema_version": 1, "region": null },
    "settings": {
      "retention_days": 7,
      "pre_roll_seconds": 10,
      "post_roll_seconds": 10,
      "clip_part_seconds": 60,
      "confidence_threshold": 0.6
    }
  },
  "clips": [
    {
      "part_number": 1,
      "source_manifest_ref": "manifests/incident-2026-10-08-100000.json",
      "status": "ready",
      "filepath": "recordings/incident-2026-10-08-100000.mp4",
      "size_bytes": 1048576,
      "recorded_start_at": "2026-10-08T09:59:50Z",
      "recorded_end_at": "2026-10-08T10:00:30Z",
      "source_ready_at": "2026-10-08T10:00:31Z",
      "expires_at": "2026-10-15T10:00:30Z"
    }
  ]
}
```

Replace the example camera UUID, paths, timestamps, size, and configuration with
real values. `source_manifest_ref` identifies the recorder's recoverable source
manifest; it is required by the existing schema. Clips default to `pending` and
require `part_number`, `source_manifest_ref`, and `expires_at`. A `ready` clip also
requires its path, positive file size, recording start/end, and source-ready time.
The API stores metadata; it does not upload or finalize video files.

Events default to `capturing`, with no `closed_at` or `end_reason`. Completed
events require both fields and `end_reason="person_absent"`; interrupted events
require an interruption reason listed in `/docs`. `clips` may be omitted for
metadata-only events. Event/clip updates and media jobs are not implemented by
these routes. Until an update route exists, the recorder should submit one
completed or interrupted event when recording finishes, including its clips,
instead of posting a separate capturing event at the start.

The worker's current two-field POST must be updated to this contract before it
can submit recordings successfully. Its recording directory must also match
`sentinel/recordings/` if files are to be downloaded through the video endpoint.

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
