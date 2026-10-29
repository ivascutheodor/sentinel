"""unique camera names, ignoring case

Revision ID: 01f7729daa10
Revises: b7c1d9e4f2a6
Create Date: 2026-10-29 13:09:23.121224

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01f7729daa10"
down_revision: str | Sequence[str] | None = "b7c1d9e4f2a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The worker identifies its camera by name. An index on lower(name) also refuses
    # "Entrance" next to "entrance". Fails if such duplicates already exist: rename one first.
    op.create_index(
        "uq_cameras_name_lower", "cameras", [sa.literal_column("lower(name)")], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_cameras_name_lower", table_name="cameras")
