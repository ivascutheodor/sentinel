"""Login rate limiting, counted from the failed logins already written to `audit_logs`.

Using the audit table instead of a counter in memory means the limit survives restarts and
works with several backend processes, and needs no new table.
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import AuditOutcome
from app.db.models import AuditLog

LOGIN_WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_USERNAME = 5
MAX_FAILURES_PER_IP = 20

# Counted failures. Refused attempts are audited under another action, so hammering the
# login while blocked does not keep extending the block.
FAILED_LOGIN = "session.login"
THROTTLED_LOGIN = "session.login_throttled"


def login_details(username: str, ip: str | None) -> dict[str, str | None]:
    """Stored with each failed or refused login; what the limits are counted by."""
    return {"username": username, "ip": ip}


def login_retry_after(session: Session, username: str, ip: str | None, now: datetime) -> int | None:
    """Seconds until this username/IP may try again, or `None` if it may try now.

    The username limit applies whether or not the account exists, so a 429 does not reveal
    which usernames are real.
    """
    recent_failures = select(AuditLog.occurred_at).where(
        AuditLog.action == FAILED_LOGIN,
        AuditLog.outcome == AuditOutcome.DENIED,
        AuditLog.occurred_at > now - LOGIN_WINDOW,
    )
    limits = [(AuditLog.details["username"].astext == username, MAX_FAILURES_PER_USERNAME)]
    if ip is not None:
        limits.append((AuditLog.details["ip"].astext == ip, MAX_FAILURES_PER_IP))

    waits = []
    for condition, limit in limits:
        newest = session.scalars(
            recent_failures.where(condition).order_by(AuditLog.occurred_at.desc()).limit(limit)
        ).all()
        if len(newest) >= limit:
            # Allowed again once the oldest of the last `limit` failures leaves the window.
            waits.append(newest[-1] + LOGIN_WINDOW - now)
    if not waits:
        return None
    return max(1, math.ceil(max(waits).total_seconds()))
