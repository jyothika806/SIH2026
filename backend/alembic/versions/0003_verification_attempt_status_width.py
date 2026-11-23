"""Widen verification attempt status for consent revocation audit states."""

import sqlalchemy as sa
from alembic import op

revision = "0003_attempt_status_width"
down_revision = "0002_phase2_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "verification_attempts",
        "status",
        existing_type=sa.String(length=24),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is disabled because consent-revocation status values may exceed "
        "the previous column width."
    )
