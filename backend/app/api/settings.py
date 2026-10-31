from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.api.deps import AdminDep, SessionDep
from app.db.enums import AuditOutcome
from app.db.models import SystemSettings
from app.schemas.settings import SystemSettingsResponse, SystemSettingsUpdate
from app.services.audit import audit
from app.services.system_settings import get_system_settings

router = APIRouter(prefix="/settings", tags=["Settings"])

EFFECTS = """
When a change takes effect:

- `retention_days`: clips saved from now on; existing clips keep their `expires_at`.
- `session_absolute_seconds`: logins from now on.
- `session_idle_seconds`: immediately, also for sessions already open.
- `pre_roll_seconds`, `post_roll_seconds`, `clip_part_seconds`, `confidence_threshold`:
  stored, but not used yet; the worker still reads its own `.env`.
"""


@router.get("", response_model=SystemSettingsResponse)
def read_settings(session: SessionDep, admin: AdminDep) -> SystemSettings:
    return get_system_settings(session)


@router.patch("", response_model=SystemSettingsResponse, description=EFFECTS)
def update_settings(
    body: SystemSettingsUpdate, session: SessionDep, admin: AdminDep
) -> SystemSettings:
    row = get_system_settings(session)
    changes = {
        field: value
        for field, value in body.model_dump(exclude_unset=True).items()
        if getattr(row, field) != value
    }
    if not changes:
        return row

    # Merge first, then check: a request may change only one of the two.
    idle = changes.get("session_idle_seconds", row.session_idle_seconds)
    absolute = changes.get("session_absolute_seconds", row.session_absolute_seconds)
    if idle > absolute:
        raise HTTPException(
            status_code=422,
            detail=(
                f"session_idle_seconds ({idle}) must not exceed "
                f"session_absolute_seconds ({absolute})."
            ),
        )

    old_values = {field: getattr(row, field) for field in changes}
    for field, value in changes.items():
        setattr(row, field, value)
    row.updated_at = datetime.now(UTC)
    audit(
        session,
        "settings.update",
        AuditOutcome.SUCCESS,
        user=admin,
        resource=("system_settings", "1"),
        details={"changes": {field: [old_values[field], changes[field]] for field in changes}},
    )
    session.commit()
    return row
