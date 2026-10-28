from sqlalchemy.orm import Session

from app.db.models import SystemSettings

SYSTEM_SETTINGS_ID = 1


def get_system_settings(session: Session) -> SystemSettings:
    """The installation-wide settings row (`id = 1`), seeded by a migration."""
    system_settings = session.get(SystemSettings, SYSTEM_SETTINGS_ID)
    if system_settings is None:
        raise RuntimeError("system_settings row is missing; run `uv run alembic upgrade head`.")
    return system_settings
