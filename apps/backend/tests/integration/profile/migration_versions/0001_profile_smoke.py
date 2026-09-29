"""Create a marker table to prove the Alembic lifecycle."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_profile_smoke"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the marker object."""

    op.create_table(
        "profile_migration_smoke",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove the marker object."""

    op.drop_table("profile_migration_smoke")
