"""Create the original OptimalRide tables on an empty database only."""

from alembic import op
from sqlalchemy import inspect, text

from backend.app.db.models import Base

revision = "0001_fresh_baseline"
down_revision = None
branch_labels = None
depends_on = None

LEGACY_TABLES = (
    "users",
    "rides",
    "mid_route_requests",
    "telemetry",
    "modal_shift_suggestions",
    "otp_logs",
    "consensus_votes",
    "fare_splits",
    "emergency_incidents",
    "guardian_mode_sessions",
    "driver_profiles",
    "document_verifications",
    "ride_ratings",
    "wallets",
    "transactions",
    "notifications",
)
SYSTEM_TABLES = {"alembic_version", "geometry_columns", "spatial_ref_sys"}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    all_tables = set(inspector.get_table_names())
    existing = all_tables - SYSTEM_TABLES
    if "alembic_version" in all_tables:
        version_count = bind.execute(
            text("SELECT COUNT(*) FROM alembic_version")
        ).scalar_one()
        if version_count:
            raise RuntimeError(
                "Fresh baseline refused because the database already has migration history."
            )
    if existing:
        raise RuntimeError(
            "Fresh baseline refused because database tables already exist. "
            "Inspect and back up the existing database, then stamp only after schema review."
        )
    if bind.dialect.name != "postgresql":
        raise RuntimeError("The fresh baseline requires PostgreSQL with PostGIS.")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    tables = [Base.metadata.tables[name] for name in LEGACY_TABLES]
    Base.metadata.create_all(bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    raise RuntimeError(
        "Baseline downgrade is intentionally disabled to prevent data loss."
    )
