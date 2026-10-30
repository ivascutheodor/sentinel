"""general-purpose scope: drop clinic wording from table comments

Revision ID: 921f8dd853a6
Revises: 01f7729daa10
Create Date: 2026-10-31 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "921f8dd853a6"
down_revision: str | Sequence[str] | None = "01f7729daa10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Sentinel is a general-purpose system now: one installation serves one organization of
# any kind, so "single-clinic" becomes "single-tenant". The rest of each comment is unchanged.
CAMERAS_REST = (
    " camera identity survives changes of name, address and credentials. "
    "Exactly one recorder owns a camera at a time. Source/ROI changes while capturing "
    "require an audited stop/restart; do not silently change an open event. Set "
    "is_enabled=false to stop monitoring; this does not by itself revoke archival "
    "access."
)
USERS_REST = (
    " accounts. Deactivate rather than hard-delete accounts referenced "
    "by historical records. Authentication must check is_active. A role change or "
    "deactivation also invalidates affected sessions/live authorizations."
)
CAMERAS_OLD, CAMERAS_NEW = "Single-clinic" + CAMERAS_REST, "Single-tenant" + CAMERAS_REST
USERS_OLD, USERS_NEW = "Single-clinic" + USERS_REST, "Single-tenant" + USERS_REST


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table_comment("cameras", CAMERAS_NEW, existing_comment=CAMERAS_OLD)
    op.create_table_comment("users", USERS_NEW, existing_comment=USERS_OLD)


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table_comment("cameras", CAMERAS_OLD, existing_comment=CAMERAS_NEW)
    op.create_table_comment("users", USERS_OLD, existing_comment=USERS_NEW)
