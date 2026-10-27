from typing import Any

from sqlalchemy.orm import Session

from app.db.enums import AuditOutcome
from app.db.models import AuditLog, User


def audit(
    session: Session,
    action: str,
    outcome: AuditOutcome,
    *,
    user: User | None = None,
    service: str | None = None,
    resource: tuple[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Adds an `audit_logs` row to the session; the caller commits it."""
    if user is not None:
        actor_type = "user"
    elif service is not None:
        actor_type = "system"
    else:
        actor_type = "anonymous"
    resource_type, resource_id = resource if resource is not None else (None, None)
    session.add(
        AuditLog(
            actor_type=actor_type,
            actor_user_id=user.id if user is not None else None,
            actor_service=service,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            details=details,
        )
    )
