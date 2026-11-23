import importlib.util
import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from backend.app.api.v1.core.config import Settings
from backend.app.api.core.security import AuthenticatedPrincipal
from backend.app.api.v1 import admin, auth
from backend.app.api.v1.driver import BiometricConsentRequest, record_biometric_consent
from backend.app.services.phone_numbers import normalize_phone
from backend.app.services import rate_limiter
from backend.app.db.models import OtpLog, UserRole
from backend.app.api.v1.rides import RideBookingRequest, handle_initial_booking
from backend.app.core.log_redaction import SensitiveDataFilter
from scripts import phase2_migration_preflight


ROOT = Path(__file__).resolve().parents[2]


def _load_revision(filename: str, module_name: str):
    path = ROOT / "backend" / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_log_filter_redacts_otp_phone_licence_and_image():
    record = logging.LogRecord(
        "security-test",
        logging.INFO,
        __file__,
        1,
        "OTP code: %s phone=%s licence=%s image=data:image/png;base64,%s",
        ("123456", "+919876543210", "KA-01-AB1234", "A" * 512),
        None,
    )

    assert SensitiveDataFilter().filter(record)
    message = record.getMessage()
    assert "123456" not in message
    assert "+919876543210" not in message
    assert "KA-01-AB1234" not in message
    assert "A" * 512 not in message
    assert "[REDACTED_OTP]" in message
    assert "[REDACTED_PHONE]" in message
    assert "[REDACTED_LICENCE]" in message
    assert "[REDACTED_IMAGE]" in message


def test_production_settings_require_real_sms_credentials():
    with pytest.raises(ValueError, match="complete Twilio SMS credentials"):
        Settings(
            environment="production",
            otp_hmac_key="test-key",
        )

    with pytest.raises(ValueError, match="DEV_OTP_CODE"):
        Settings(
            environment="production",
            otp_hmac_key="test-key",
            dev_otp_code="123456",
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_phone_number="+15555550100",
        )

    configured = Settings(
        environment="production",
        otp_hmac_key="test-key",
        twilio_account_sid="AC123",
        twilio_auth_token="token",
        twilio_phone_number="+15555550100",
    )
    assert configured.sms_provider == "twilio"


def test_phone_normalization_is_canonical_and_rejects_invalid_values():
    assert normalize_phone("(415) 555-2671", "US") == "+14155552671"
    assert normalize_phone("+1 415 555 2671", "IN") == "+14155552671"
    with pytest.raises(ValueError, match="invalid"):
        normalize_phone("not a phone", "US")


def test_read_only_migration_preflight_counts_phone_changes_without_values(monkeypatch):
    monkeypatch.setattr(
        phase2_migration_preflight,
        "get_settings",
        lambda: SimpleNamespace(phone_default_region="IN"),
    )
    counts = phase2_migration_preflight._account_phone_counts(
        [
            (1, "9876543210"),
            (2, "+919876543210"),
            (3, "not a phone"),
        ]
    )
    assert counts == {
        "account_phone_normalization_needed": 1,
        "invalid_account_phones": 1,
        "account_phone_collision_rows": 2,
    }


def test_public_registration_rejects_admin_role():
    with pytest.raises(ValueError):
        auth.UserRegistration(phone="+14155552671", role="admin")


def test_active_otp_constraint_uses_a_static_partial_predicate():
    index = next(item for item in OtpLog.__table__.indexes if item.name == "uq_active_otp_phone")
    predicate = str(index.dialect_options["postgresql"]["where"]).lower()
    assert index.unique
    assert "consumed_at is null" in predicate
    assert "otp_hash is not null" in predicate
    assert "now(" not in predicate


def test_access_tokens_require_issuer_audience_expiry_and_subject(monkeypatch):
    monkeypatch.setattr(
        auth.settings,
        "jwt_secret_key",
        "test-jwt-secret-that-is-at-least-32-bytes",
    )
    monkeypatch.setattr(auth.settings, "jwt_issuer", "phase2-test-issuer")
    monkeypatch.setattr(auth.settings, "jwt_audience", "phase2-test-audience")
    token = auth.create_access_token(
        {"sub": "42", "phone": "+14155552671", "role": "passenger"}
    )
    claims = auth.verify_token(token)
    assert claims["sub"] == "42"
    assert claims["iss"] == "phase2-test-issuer"
    assert claims["aud"] == "phase2-test-audience"
    assert claims["exp"] > claims["iat"]
    wrong_audience = {**claims, "aud": "another-service"}
    invalid_token = jwt.encode(
        wrong_audience,
        auth.settings.jwt_secret_key,
        algorithm=auth.settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException):
        auth.verify_token(invalid_token)


@pytest.mark.asyncio
async def test_production_rate_limiting_fails_closed_without_redis(monkeypatch):
    monkeypatch.setattr(rate_limiter.settings, "environment", "production")
    monkeypatch.setattr(rate_limiter.settings, "otp_hmac_key", "test-only-hmac-key")
    monkeypatch.setattr(rate_limiter, "redis_client", None)
    with pytest.raises(HTTPException) as error:
        await rate_limiter.consume_rate_limit(
            db=None,
            scope="verify-phone",
            identifier="+14155552671",
            limit=5,
            window_seconds=60,
        )
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_database_rate_limit_cleanup_is_bounded_and_repeatable(monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    monkeypatch.setattr(rate_limiter.settings, "rate_limit_bucket_retention_hours", 24)

    class FakeDatabase:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return SimpleNamespace(rowcount=2)

    database = FakeDatabase()
    removed = await rate_limiter.cleanup_expired_rate_limit_buckets(
        database, datetime(2030, 1, 2, tzinfo=timezone.utc)
    )
    assert removed == 2
    assert database.statement.table.name == "rate_limit_buckets"


@pytest.mark.asyncio
async def test_admin_authorization_uses_database_role_not_token_role():
    class FakeDatabase:
        def __init__(self, account):
            self.account = account

        async def scalar(self, _statement):
            return self.account

    account = type(
        "Account", (), {"id": 7, "role": UserRole.ADMIN, "is_active": True}
    )()
    reviewer_id = await admin._require_admin(
        AuthenticatedPrincipal(user_id=7, role="passenger", phone=None),
        FakeDatabase(account),
    )
    assert reviewer_id == 7

    account.role = UserRole.PASSENGER
    with pytest.raises(HTTPException) as error:
        await admin._require_admin(
            AuthenticatedPrincipal(user_id=7, role="admin", phone=None),
            FakeDatabase(account),
        )
    assert error.value.status_code == 403


def test_booking_capacity_is_checked_before_route_or_database_access(monkeypatch):
    from backend.app.api.v1 import rides

    monkeypatch.setitem(rides.settings.vehicle_capacities, "bike", 1)
    request = RideBookingRequest(
        pickup_lat=12.9,
        pickup_lon=77.5,
        dropoff_lat=13.0,
        dropoff_lon=77.6,
        vehicle_type="bike",
        seats_required=2,
    )

    with pytest.raises(HTTPException) as error:
        import asyncio

        asyncio.run(handle_initial_booking(request, passenger_id=1, db=None))
    assert error.value.status_code == 422
    assert "capacity" in error.value.detail.lower()


def test_only_driver_can_record_biometric_consent():
    with pytest.raises(HTTPException) as error:
        import asyncio

        asyncio.run(
            record_biometric_consent(
                BiometricConsentRequest(granted=True, consent_text_version="v1"),
                current_user=AuthenticatedPrincipal(
                    user_id=1, role="passenger", phone="+14155552671"
                ),
                db=None,
            )
        )
    assert error.value.status_code == 403


def test_risk_request_contract_avoids_demographic_fields():
    from backend.app.api.v1.risk import RiskEvaluationRequest

    fields = {name.lower() for name in RiskEvaluationRequest.model_fields}
    assert not fields.intersection({"age", "gender", "race", "religion", "ethnicity"})


def test_migration_invalidates_plaintext_and_unlocked_ride_otps():
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_correction_migration"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE otp_logs "
                "(id INTEGER PRIMARY KEY, otp TEXT, otp_hash TEXT, consumed_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE rides "
                "(id INTEGER PRIMARY KEY, otp TEXT, otp_hash TEXT, otp_unlocked BOOLEAN, "
                "otp_expires_at DATETIME, otp_consumed_at DATETIME)"
            )
        )
        connection.execute(
            text("INSERT INTO otp_logs (id, otp, otp_hash) VALUES (1, '123456', 'old-hash')")
        )
        connection.execute(
            text(
                "INSERT INTO rides "
                "(id, otp, otp_hash, otp_unlocked, otp_expires_at) "
                "VALUES (1, NULL, 'old-hash', 1, '2030-01-01')"
            )
        )

        migration._invalidate_legacy_otps(connection)

        otp = connection.execute(
            text("SELECT otp, otp_hash, consumed_at FROM otp_logs WHERE id=1")
        ).one()
        ride = connection.execute(
            text(
                "SELECT otp, otp_hash, otp_unlocked, otp_expires_at, otp_consumed_at "
                "FROM rides WHERE id=1"
            )
        ).one()
        assert otp.otp is None and otp.otp_hash is None and otp.consumed_at is not None
        assert all(value is None for value in (ride.otp, ride.otp_hash, ride.otp_expires_at))
        assert not ride.otp_unlocked and ride.otp_consumed_at is not None
    engine.dispose()


def test_migration_normalizes_legacy_account_phones_without_losing_accounts():
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_phone_normalization_migration"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, phone TEXT UNIQUE)")
        )
        connection.execute(
            text("INSERT INTO users (id, phone) VALUES (1, '9876543210')")
        )
        migration._normalize_existing_user_phones(connection)
        row = connection.execute(
            text("SELECT id, phone FROM users WHERE id=1")
        ).one()
        assert row.id == 1
        assert row.phone == "+919876543210"
    engine.dispose()


def test_migration_refuses_sensitive_data_without_backup_acknowledgement(monkeypatch):
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_preflight_migration"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, phone TEXT UNIQUE)")
        )
        connection.execute(
            text(
                "CREATE TABLE rides "
                "(id INTEGER PRIMARY KEY, passenger_id INTEGER, status TEXT, "
                "seats_occupied INTEGER, seats_total INTEGER, otp TEXT)"
            )
        )
        connection.execute(
            text("CREATE TABLE otp_logs (id INTEGER PRIMARY KEY, otp TEXT)")
        )
        connection.execute(
            text(
                "CREATE TABLE driver_profiles "
                "(id INTEGER PRIMARY KEY, license_number TEXT, license_number_last4 TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO otp_logs (id, otp) VALUES (1, '123456')"
            )
        )

        monkeypatch.delenv("PHASE2_BACKUP_ACKNOWLEDGED", raising=False)
        monkeypatch.delenv("PHASE2_ALLOW_IRREVERSIBLE_MIGRATION", raising=False)
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        with pytest.raises(RuntimeError, match="Verify a restorable backup"):
            migration._preflight()
    engine.dispose()


@pytest.mark.parametrize(
    ("statement", "expected_count"),
    [
        (
            "INSERT INTO otp_logs (id, phone, otp_hash) VALUES (1, '+14155552671', 'hash')",
            "OTP hashes=1",
        ),
        (
            "INSERT INTO rides (id, passenger_id, status, seats_occupied, seats_total, otp_unlocked) "
            "VALUES (1, 1, 'SEARCHING', 0, 4, 1)",
            "unlocked ride OTPs=1",
        ),
    ],
)
def test_migration_preflight_counts_hashes_and_unlocked_ride_states(
    monkeypatch, statement, expected_count
):
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_preflight_count_migration"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, phone TEXT UNIQUE)")
        )
        connection.execute(
            text(
                "CREATE TABLE rides (id INTEGER PRIMARY KEY, passenger_id INTEGER, status TEXT, "
                "seats_occupied INTEGER, seats_total INTEGER, otp TEXT, otp_hash TEXT, "
                "otp_unlocked BOOLEAN, otp_expires_at DATETIME, otp_consumed_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE otp_logs (id INTEGER PRIMARY KEY, phone TEXT, otp TEXT, "
                "otp_hash TEXT, consumed_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE driver_profiles (id INTEGER PRIMARY KEY, license_number TEXT, "
                "license_number_last4 TEXT)"
            )
        )
        connection.execute(text(statement))
        monkeypatch.delenv("PHASE2_BACKUP_ACKNOWLEDGED", raising=False)
        monkeypatch.delenv("PHASE2_ALLOW_IRREVERSIBLE_MIGRATION", raising=False)
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        with pytest.raises(RuntimeError, match=expected_count):
            migration._preflight()
    engine.dispose()


def test_migration_preflight_rejects_duplicate_active_otp_challenges(monkeypatch):
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_duplicate_otp_migration"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, phone TEXT UNIQUE)")
        )
        connection.execute(
            text(
                "CREATE TABLE rides (id INTEGER PRIMARY KEY, passenger_id INTEGER, status TEXT, "
                "seats_occupied INTEGER, seats_total INTEGER)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE otp_logs (id INTEGER PRIMARY KEY, phone TEXT, otp_hash TEXT, "
                "consumed_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE driver_profiles (id INTEGER PRIMARY KEY, license_number TEXT, "
                "license_number_last4 TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO otp_logs (id, phone, otp_hash) VALUES "
                "(1, '+14155552671', 'hash-1'), (2, '+14155552671', 'hash-2')"
            )
        )
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        with pytest.raises(RuntimeError, match="Duplicate active OTP challenges"):
            migration._preflight()
    engine.dispose()


def test_legacy_licence_with_existing_last4_is_still_encrypted(monkeypatch):
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_licence_encryption_migration"
    )
    key = Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY", key.decode("ascii"))
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE driver_profiles "
                "(id INTEGER PRIMARY KEY, license_number TEXT, license_number_last4 TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO driver_profiles (id, license_number, license_number_last4) "
                "VALUES (1, 'KA-01-AB1234', '1234')"
            )
        )

        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        migration._encrypt_legacy_licences()

        encrypted = connection.execute(
            text("SELECT license_number, license_number_last4 FROM driver_profiles WHERE id=1")
        ).one()
        assert encrypted.license_number != "KA-01-AB1234"
        assert Fernet(key).decrypt(encrypted.license_number.encode()).decode() == "KA-01-AB1234"
        assert encrypted.license_number_last4 == "1234"
    engine.dispose()


def test_backup_verification_checks_sqlite_integrity_and_table_counts(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "backup_phase2_under_test", ROOT / "scripts" / "backup_phase2.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backup script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source = tmp_path / "source.sqlite"
    output = tmp_path / "backup.sqlite"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO records (value) VALUES ('preserved')")

    module.backup(f"sqlite:///{source.as_posix()}", output)
    assert output.exists()
    assert module._sqlite_table_counts(source) == module._sqlite_table_counts(output)


def test_migration_downgrade_never_restores_plaintext_otps():
    migration = _load_revision(
        "0002_phase2_foundation.py", "phase2_downgrade_migration"
    )
    with pytest.raises(RuntimeError, match="must never be restored"):
        migration.downgrade()


def test_fresh_baseline_refuses_populated_database(monkeypatch):
    migration = _load_revision(
        "0001_fresh_baseline.py", "phase2_fresh_baseline_guard"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        with pytest.raises(RuntimeError, match="tables already exist"):
            migration.upgrade()
    engine.dispose()
