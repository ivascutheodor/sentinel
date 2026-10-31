"""seed system_settings and protect the row

Revision ID: b7c1d9e4f2a6
Revises: ea5ce070565b
Create Date: 2026-10-28 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1d9e4f2a6"
down_revision: str | Sequence[str] | None = "ea5ce070565b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The column defaults are the seed values (retention 7 days, sessions 12 h / 30 min, ...).
    # ON CONFLICT keeps a row someone already inserted by hand.
    op.execute("INSERT INTO system_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

    # The app reads this row on every login and event, so it must not disappear.
    op.execute(
        """
        CREATE FUNCTION system_settings_prevent_removal() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'system_settings row cannot be removed; update it instead';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER system_settings_no_delete
        BEFORE DELETE ON system_settings
        FOR EACH ROW EXECUTE FUNCTION system_settings_prevent_removal()
        """
    )
    op.execute(
        """
        CREATE TRIGGER system_settings_no_truncate
        BEFORE TRUNCATE ON system_settings
        FOR EACH STATEMENT EXECUTE FUNCTION system_settings_prevent_removal()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER system_settings_no_truncate ON system_settings")
    op.execute("DROP TRIGGER system_settings_no_delete ON system_settings")
    op.execute("DROP FUNCTION system_settings_prevent_removal()")
    op.execute("DELETE FROM system_settings WHERE id = 1")
