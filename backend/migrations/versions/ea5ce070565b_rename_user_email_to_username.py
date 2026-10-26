"""rename user email to username

Revision ID: ea5ce070565b
Revises: 2feed91c7392
Create Date: 2026-10-23 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea5ce070565b"
down_revision: str | Sequence[str] | None = "2feed91c7392"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Lower-case letters, digits, dot, underscore and hyphen; this also rules out
# surrounding spaces, so no separate trim check is needed.
USERNAME_CHECK = "username ~ '^[a-z0-9._-]{3,50}$'"
EMAIL_CHECK = "email = lower(btrim(email)) AND length(email) BETWEEN 3 AND 254"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("email", "users", type_="check")
    op.alter_column("users", "email", new_column_name="username")
    # The initial migration left the unique constraint unnamed, so PostgreSQL
    # called it users_email_key; renaming keeps upgraded and fresh databases alike.
    op.execute("ALTER TABLE users RENAME CONSTRAINT users_email_key TO users_username_key")
    op.create_check_constraint("username", "users", USERNAME_CHECK)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("username", "users", type_="check")
    op.execute("ALTER TABLE users RENAME CONSTRAINT users_username_key TO users_email_key")
    op.alter_column("users", "username", new_column_name="email")
    op.create_check_constraint("email", "users", EMAIL_CHECK)
