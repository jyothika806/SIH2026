"""Add secure verification, lifecycle, rate-limit, and idempotency foundations."""

from datetime import datetime, timezone
import os

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import inspect, text

from backend.app.db.models import Base
from backend.app.services.phone_numbers import normalize_phone
from backend.app.api.v1.core.config import get_settings

revision = "0002_phase2_foundation"
down_revision = "0001_fresh_baseline"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "seat_reservations",
    "idempotency_records",
    "rate_limit_buckets",
    "driver_licences",
    "biometric_consents",
    "face_templates",
    "verification_attempts",
    "verification_audit_log",
    "migration_runs",
)


def _add_missing_columns(table_name: str, columns: list[sa.Column]) -> None:
    inspector = inspect(op.get_bind())
    current = {column["name"] for column in inspector.get_columns(table_name)}
    for column in columns:
        if column.name not in current:
            op.add_column(table_name, column)


def _preflight() -> tuple[int, int, int, int, int]:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for required in ("users", "rides", "otp_logs", "driver_profiles"):
        if required not in tables:
            raise RuntimeError(f"Existing database is missing required table: {required}")

    duplicate = bind.execute(
        text(
            "SELECT passenger_id FROM rides "
            "WHERE upper(CAST(status AS TEXT)) IN "
            "('REQUESTED', 'SEARCHING', 'DRIVER_ASSIGNED', 'ARRIVED') "
            "GROUP BY passenger_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError("Multiple active bookings exist for a passenger; resolve before migration.")
    invalid_seats = bind.execute(
        text(
            "SELECT id FROM rides "
            "WHERE seats_occupied < 0 OR seats_total < 0 OR seats_occupied > seats_total LIMIT 1"
        )
    ).first()
    if invalid_seats:
        raise RuntimeError("Invalid ride seat counts exist; resolve before migration.")

    otp_columns = {item["name"] for item in inspector.get_columns("otp_logs")}
    ride_columns = {item["name"] for item in inspector.get_columns("rides")}
    profile_columns = {item["name"] for item in inspector.get_columns("driver_profiles")}
    normalized_user_phones: dict[str, int] = {}
    phone_normalization_count = 0
    for user in bind.execute(text("SELECT id, phone FROM users")).all():
        try:
            normalized = normalize_phone(
                user.phone, get_settings().phone_default_region
            )
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "An existing account has an invalid phone number; migration stopped."
            ) from error
        previous_user_id = normalized_user_phones.get(normalized)
        if previous_user_id is not None and previous_user_id != user.id:
            raise RuntimeError(
                "Existing account phone numbers collide after normalization; "
                "resolve manually before migration."
            )
        normalized_user_phones[normalized] = user.id
        if normalized != user.phone:
            phone_normalization_count += 1
    if {"consumed_at", "otp_hash"}.issubset(otp_columns):
        duplicate_otp = bind.execute(
            text(
                "SELECT phone FROM otp_logs "
                "WHERE consumed_at IS NULL AND otp_hash IS NOT NULL "
                "GROUP BY phone HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicate_otp:
            raise RuntimeError(
                "Duplicate active OTP challenges exist for a phone; resolve manually "
                "before migration."
            )
    plaintext_otp_count = 0
    otp_hash_count = 0
    unlocked_ride_otp_count = 0
    if "otp" in otp_columns:
        plaintext_otp_count += bind.execute(
            text("SELECT COUNT(*) FROM otp_logs WHERE otp IS NOT NULL")
        ).scalar_one()
    if "otp_hash" in otp_columns:
        otp_hash_count += bind.execute(
            text("SELECT COUNT(*) FROM otp_logs WHERE otp_hash IS NOT NULL")
        ).scalar_one()
    if "otp" in ride_columns:
        plaintext_otp_count += bind.execute(
            text("SELECT COUNT(*) FROM rides WHERE otp IS NOT NULL")
        ).scalar_one()
    if "otp_hash" in ride_columns:
        otp_hash_count += bind.execute(
            text("SELECT COUNT(*) FROM rides WHERE otp_hash IS NOT NULL")
        ).scalar_one()
    if "otp_unlocked" in ride_columns:
        unlocked_ride_otp_count = bind.execute(
            text("SELECT COUNT(*) FROM rides WHERE otp_unlocked IS TRUE")
        ).scalar_one()
    legacy_licence_count = 0
    if "license_number" in profile_columns:
        legacy_filter = (
            "(license_number_last4 IS NULL OR license_number NOT LIKE 'gAAAA%') AND "
            if "license_number_last4" in profile_columns
            else "license_number NOT LIKE 'gAAAA%' AND "
        )
        legacy_licence_count = bind.execute(
            text(
                "SELECT COUNT(*) FROM driver_profiles WHERE "
                + legacy_filter
                + "license_number IS NOT NULL AND license_number != ''"
            )
        ).scalar_one()
    if (
        plaintext_otp_count
        or otp_hash_count
        or unlocked_ride_otp_count
        or legacy_licence_count
        or phone_normalization_count
    ):
        if os.getenv("PHASE2_BACKUP_ACKNOWLEDGED") != "YES":
            raise RuntimeError(
                "Migration preflight found data requiring invalidation or encryption "
                f"(plaintext OTPs={plaintext_otp_count}, OTP hashes={otp_hash_count}, "
                f"unlocked ride OTPs={unlocked_ride_otp_count}, "
                f"legacy licence values={legacy_licence_count}, "
                f"account phones normalized={phone_normalization_count}). "
                "Verify a restorable "
                "backup, obtain separate approval, then set "
                "PHASE2_BACKUP_ACKNOWLEDGED=YES."
            )
        if os.getenv("PHASE2_ALLOW_IRREVERSIBLE_MIGRATION") != "YES":
            raise RuntimeError(
                "This migration invalidates existing OTP credentials and encrypts legacy "
                "licence data. Separate approval is required; set "
                "PHASE2_ALLOW_IRREVERSIBLE_MIGRATION=YES only then."
            )
    if legacy_licence_count and not os.getenv("FERNET_KEY"):
        raise RuntimeError("FERNET_KEY is required to encrypt existing driver licence numbers.")
    return (
        plaintext_otp_count,
        otp_hash_count,
        unlocked_ride_otp_count,
        legacy_licence_count,
        phone_normalization_count,
    )


def _normalize_existing_user_phones(bind) -> None:
    region = get_settings().phone_default_region
    for user in bind.execute(text("SELECT id, phone FROM users")).all():
        normalized = normalize_phone(user.phone, region)
        if normalized != user.phone:
            bind.execute(
                text("UPDATE users SET phone=:phone WHERE id=:id"),
                {"phone": normalized, "id": user.id},
            )


def _encrypt_legacy_licences() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        text(
            "SELECT id, license_number FROM driver_profiles "
            "WHERE license_number IS NOT NULL AND license_number != '' "
            "AND (license_number_last4 IS NULL OR license_number NOT LIKE 'gAAAA%')"
        )
    ).all()
    if not rows:
        return
    fernet = Fernet(os.environ["FERNET_KEY"].encode("ascii"))
    for row in rows:
        value = row.license_number
        if value.startswith("gAAAA"):
            try:
                plaintext = fernet.decrypt(value.encode()).decode()
            except InvalidToken as error:
                raise RuntimeError(
                    "A legacy driver licence value cannot be decrypted; migration stopped."
                ) from error
        else:
            plaintext = value
        last4 = plaintext[-4:]
        encrypted = fernet.encrypt(plaintext.encode()).decode()
        bind.execute(
            text(
                "UPDATE driver_profiles SET license_number=:encrypted, "
                "license_number_last4=:last4 WHERE id=:id"
            ),
            {"encrypted": encrypted, "last4": last4, "id": row.id},
        )


def _invalidate_legacy_otps(bind) -> None:
    now = datetime.now(timezone.utc)
    bind.execute(
        text(
            "UPDATE otp_logs SET otp=NULL, otp_hash=NULL, consumed_at=:now "
            "WHERE otp IS NOT NULL OR otp_hash IS NOT NULL"
        ),
        {"now": now},
    )
    bind.execute(
        text(
            "UPDATE rides SET otp=NULL, otp_hash=NULL, otp_unlocked=false, "
            "otp_expires_at=NULL, otp_consumed_at=:now "
            "WHERE otp IS NOT NULL OR otp_hash IS NOT NULL OR otp_unlocked IS TRUE"
        ),
        {"now": now},
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("Phase 2 schema migrations require PostgreSQL with PostGIS.")
    _preflight()

    _add_missing_columns(
        "rides",
        [
            sa.Column("otp_hash", sa.String(64), nullable=True),
            sa.Column("otp_consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("seats_required", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("search_expires_at", sa.DateTime(timezone=True), nullable=True),
        ],
    )
    _add_missing_columns(
        "otp_logs",
        [
            sa.Column("otp_hash", sa.String(64), nullable=True),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verify_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("request_ip", sa.String(64), nullable=True),
        ],
    )
    _add_missing_columns(
        "driver_profiles",
        [sa.Column("license_number_last4", sa.String(4), nullable=True)],
    )
    inspector = inspect(bind)
    ride_columns = {column["name"] for column in inspector.get_columns("rides")}
    if "driver_id" in ride_columns:
        op.alter_column("rides", "driver_id", existing_type=sa.Integer(), nullable=True)
    if "otp" in ride_columns:
        op.alter_column("rides", "otp", existing_type=sa.String(length=6), type_=sa.String(length=512), nullable=True)

    # Legacy OTPs are invalidated, never copied to the hashed OTP fields.
    _invalidate_legacy_otps(bind)
    _normalize_existing_user_phones(bind)
    _encrypt_legacy_licences()
    bind.execute(
        text(
            "UPDATE driver_profiles SET verification_status='pending' "
            "WHERE coalesce(is_verified, false)=false "
            "OR coalesce(verification_status, 'pending') <> 'verified'"
        )
    )
    bind.execute(text("UPDATE rides SET seats_required=GREATEST(seats_occupied, 1)"))

    for table_name in NEW_TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)

    for table_name, name in (
        ("rides", "uq_active_passenger_booking"),
        ("otp_logs", "uq_active_otp_phone"),
    ):
        index = next(
            item
            for item in Base.metadata.tables[table_name].indexes
            if item.name == name
        )
        index.create(bind, checkfirst=True)

    constraint_names = {
        constraint.get("name")
        for constraint in inspect(bind).get_check_constraints("rides")
    }
    if "ck_rides_seat_counts" not in constraint_names:
        op.create_check_constraint(
            "ck_rides_seat_counts",
            "rides",
            "seats_occupied >= 0 AND seats_total >= 0 AND seats_occupied <= seats_total",
        )


def downgrade() -> None:
    raise RuntimeError(
        "Phase 2 downgrade is intentionally disabled: plaintext OTPs are invalidated "
        "and must never be restored. Recover from a verified backup only after sanitizing "
        "legacy OTP values."
    )
