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
uv run fastapi dev app/main.py --host 0.0.0.0
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
