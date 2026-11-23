import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import func, select
from geoalchemy2.elements import WKTElement

from backend.app.api.v1 import auth, rides
from backend.app.api.core.security import AuthenticatedPrincipal
from backend.app.api.v1.auth import OTPRequest, OTPVerification
from backend.app.api.v1.driver import BiometricConsentRequest, record_biometric_consent
from backend.app.api.v1.rides import RideBookingRequest, book_ride
from backend.app.db.models import (
    BiometricConsent,
    DriverLicence,
    DriverProfile,
    FaceTemplate,
    IdempotencyRecord,
    Ride,
    RideStatus,
    User,
    UserRole,
    VerificationAuditLog,
    VerificationAttempt,
    VehicleType,
)
from backend.app.services import (
    biometric_retention,
    otp_service,
    rate_limiter,
    verification_service,
)
from backend.app.services.utc_time import utc_now


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/request-otp",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8765),
        }
    )


@pytest.mark.asyncio
async def test_login_otp_is_generated_hashed_consumed_and_cannot_be_replayed(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        user = User(phone="+14155552671", role=UserRole.PASSENGER)
        db.add(user)
        await db.commit()

        monkeypatch.setattr(auth.settings, "environment", "test")
        monkeypatch.setattr(auth.settings, "dev_otp_code", None)
        monkeypatch.setattr(auth.settings, "otp_hmac_key", "test-only-hmac-key")
        monkeypatch.setattr(otp_service.settings, "otp_hmac_key", "test-only-hmac-key")
        monkeypatch.setattr(rate_limiter.settings, "otp_hmac_key", "test-only-hmac-key")
        delivered_codes = []

        async def capture_delivery(phone, code, user_id=None):
            assert phone == user.phone
            delivered_codes.append(code)
            return {"success": True, "delivery_status": "sent"}

        monkeypatch.setattr(auth.sms_service, "send_otp", capture_delivery)

        await auth.request_otp(
            OTPRequest(phone=user.phone, delivery_method="sms"),
            _request(),
            db,
        )
        assert len(delivered_codes) == 1
        code = delivered_codes[0]
        assert len(code) == 6 and code.isdigit()
        await db.commit()

        record = await db.scalar(
            select(auth.OtpLog).where(auth.OtpLog.phone == user.phone)
        )
        assert record is not None
        assert record.otp is None
        assert record.otp_hash is not None
        assert otp_service.verify_otp(code, record.otp_hash, "login", user.phone)

        with pytest.raises(HTTPException) as invalid:
            await auth.verify_otp(
                OTPVerification(phone=user.phone, otp="000000", role="passenger"),
                db,
            )
        assert invalid.value.status_code == 401
        await db.commit()

        response = await auth.verify_otp(
            OTPVerification(phone=user.phone, otp=code, role="passenger"),
            db,
        )
        assert response.access_token
        claims = auth.verify_token(response.access_token)
        assert claims["sub"] == str(user.id)
        assert claims["iss"] == auth.settings.jwt_issuer
        assert claims["aud"] == auth.settings.jwt_audience
        await db.commit()

        record = await db.scalar(select(auth.OtpLog).where(auth.OtpLog.id == record.id))
        assert record is not None
        assert record.otp is None and record.otp_hash is None
        assert record.consumed_at is not None

        with pytest.raises(HTTPException) as replay:
            await auth.verify_otp(
                OTPVerification(phone=user.phone, otp=code, role="passenger"),
                db,
            )
        assert replay.value.status_code == 401


@pytest.mark.asyncio
async def test_concurrent_login_otp_issuance_keeps_one_active_challenge(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        user = User(phone="+14155552672", role=UserRole.PASSENGER)
        db.add(user)
        await db.commit()
        phone = user.phone

    monkeypatch.setattr(auth.settings, "environment", "test")
    monkeypatch.setattr(auth.settings, "dev_otp_code", None)
    monkeypatch.setattr(auth.settings, "otp_hmac_key", "concurrent-test-hmac-key")
    monkeypatch.setattr(
        otp_service.settings, "otp_hmac_key", "concurrent-test-hmac-key"
    )
    monkeypatch.setattr(
        rate_limiter.settings, "otp_hmac_key", "concurrent-test-hmac-key"
    )
    delivered_codes = []

    async def capture_delivery(_phone, code, _user_id=None):
        assert _phone == phone
        delivered_codes.append(code)
        return {"success": True, "delivery_status": "sent"}

    monkeypatch.setattr(auth.sms_service, "send_otp", capture_delivery)

    async def issue_otp():
        async with phase2_db() as db:
            await auth.request_otp(
                OTPRequest(phone=phone, delivery_method="sms"),
                _request(),
                db,
            )
            await db.commit()

    await asyncio.gather(issue_otp(), issue_otp())
    assert len(delivered_codes) == 2

    async with phase2_db() as db:
        active = list(
            await db.scalars(
                select(auth.OtpLog).where(
                    auth.OtpLog.phone == phone,
                    auth.OtpLog.consumed_at.is_(None),
                    auth.OtpLog.otp_hash.is_not(None),
                )
            )
        )
        assert len(active) == 1
        assert sum(
            otp_service.verify_otp(code, active[0].otp_hash, "login", phone)
            for code in delivered_codes
        ) == 1


@pytest.mark.asyncio
async def test_booking_idempotency_replays_original_result_without_duplicate_ride(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        passenger = User(phone="+15555550124", role=UserRole.PASSENGER)
        db.add(passenger)
        await db.commit()

        async def route_geometry(*_args):
            return {
                "geometry": "77.5 12.9,77.6 13.0",
                "duration_minutes": 10,
                "distance_km": 5,
            }

        async def no_matches(*_args):
            return []

        monkeypatch.setattr(rides.matching_service, "calculate_route_geometry", route_geometry)
        monkeypatch.setattr(rides.matching_service, "find_matching_rides", no_matches)
        request = RideBookingRequest(
            pickup_lat=12.9,
            pickup_lon=77.5,
            dropoff_lat=13.0,
            dropoff_lon=77.6,
            vehicle_type="cab",
            seats_required=1,
        )
        current_user = {"sub": str(passenger.id), "role": "passenger"}

        first = await book_ride(request, "booking-key-001", current_user, db)
        await db.commit()
        replay = await book_ride(request, "booking-key-001", current_user, db)
        await db.commit()

        assert replay.id == first.id
        assert await db.scalar(select(func.count(Ride.id))) == 1
        assert await db.scalar(select(func.count(IdempotencyRecord.id))) == 1

        changed_request = request.model_copy(update={"seats_required": 2})
        with pytest.raises(HTTPException) as error:
            await book_ride(changed_request, "booking-key-001", current_user, db)
        assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_consent_grant_and_revocation_are_audited_and_affect_eligibility(phase2_db):
    async with phase2_db() as db:
        driver = User(phone="+15555550125", role=UserRole.DRIVER)
        passenger = User(phone="+15555550126", role=UserRole.PASSENGER)
        db.add_all([driver, passenger])
        await db.commit()
        db.add(
            DriverProfile(
                user_id=driver.id,
                license_expiry=date(2035, 1, 1),
                vehicle_type="cab",
                vehicle_number="TEST-125",
                vehicle_model="Test model",
                vehicle_color="Blue",
                vehicle_year=2025,
                is_verified=False,
                verification_status="pending",
                is_online=False,
            )
        )
        template = FaceTemplate(
            driver_id=driver.id,
            encrypted_embedding=b"retention-test-template",
            model_version="disabled",
            status="pending_review",
        )
        db.add(template)
        await db.flush()
        ride = Ride(
            driver_id=driver.id,
            passenger_id=passenger.id,
            vehicle_type=VehicleType.CAB,
            pickup_point=WKTElement("POINT(77.5946 12.9716)", srid=4326),
            dropoff_point=WKTElement("POINT(77.6245 12.9352)", srid=4326),
            seats_total=4,
            seats_occupied=1,
            seats_required=1,
            status=RideStatus.ARRIVED,
            otp_hash="pending-test-hash",
            otp_unlocked=False,
            otp_expires_at=utc_now() + timedelta(minutes=5),
        )
        db.add(ride)
        await db.flush()
        attempt = VerificationAttempt(
            ride_id=ride.id,
            driver_id=driver.id,
            face_template_id=template.id,
            nonce_hash="test-nonce-hash",
            status="pending",
            liveness_passed=False,
            expires_at=utc_now() + timedelta(minutes=5),
        )
        db.add(attempt)
        await db.flush()
        await db.commit()

        current_user = AuthenticatedPrincipal(
            user_id=driver.id, role="driver", phone=driver.phone
        )
        granted = await record_biometric_consent(
            BiometricConsentRequest(granted=True, consent_text_version="v1"),
            current_user,
            db,
        )
        assert granted["granted"] is True
        await db.commit()

        eligible, reasons, _ = await verification_service.driver_eligibility(
            db, driver.id, "cab", require_online=False
        )
        assert not eligible
        assert "biometric_consent_missing" not in reasons
        active = await db.scalar(
            select(func.count(BiometricConsent.id)).where(
                BiometricConsent.driver_id == driver.id,
                BiometricConsent.revoked_at.is_(None),
            )
        )
        assert active == 1

        revoked = await record_biometric_consent(
            BiometricConsentRequest(granted=False, consent_text_version="v1"),
            current_user,
            db,
        )
        assert revoked["granted"] is False
        await db.commit()

        eligible, reasons, _ = await verification_service.driver_eligibility(
            db, driver.id, "cab", require_online=False
        )
        assert not eligible and "biometric_consent_missing" in reasons
        active = await db.scalar(
            select(func.count(BiometricConsent.id)).where(
                BiometricConsent.driver_id == driver.id,
                BiometricConsent.revoked_at.is_(None),
            )
        )
        assert active == 0
        await db.refresh(ride)
        await db.refresh(attempt)
        assert ride.otp_hash is None
        assert ride.otp_unlocked is False
        assert ride.otp_expires_at is None
        assert attempt.status == "cancelled_consent_revoked"
        outcomes = list(
            await db.scalars(
                select(VerificationAuditLog.outcome)
                .where(VerificationAuditLog.driver_id == driver.id)
                .order_by(VerificationAuditLog.id)
            )
        )
        assert outcomes == ["granted", "revoked"]


@pytest.mark.asyncio
async def test_biometric_template_retention_is_idempotent_and_audited(
    phase2_db, monkeypatch
):
    monkeypatch.setattr(
        biometric_retention,
        "get_settings",
        lambda: SimpleNamespace(biometric_retention_days=365),
    )
    async with phase2_db() as db:
        driver = User(phone="+14155552673", role=UserRole.DRIVER)
        db.add(driver)
        await db.flush()
        template = FaceTemplate(
            driver_id=driver.id,
            encrypted_embedding=b"encrypted-test-embedding",
            model_version="disabled",
            status="pending_review",
            created_at=utc_now() - timedelta(days=366),
        )
        db.add(template)
        await db.commit()
        template_id = template.id

        assert await biometric_retention.cleanup_expired_biometric_templates(db) == 1
        await db.commit()
        await db.refresh(template)
        assert template.encrypted_embedding == b""
        assert template.status == "expired_retention"

        assert await biometric_retention.cleanup_expired_biometric_templates(db) == 0
        await db.commit()
        audits = list(
            await db.scalars(
                select(VerificationAuditLog).where(
                    VerificationAuditLog.action == "biometric_template_retention"
                )
            )
        )
        assert sum(item.detail.get("template_id") == template_id for item in audits) == 1


@pytest.mark.asyncio
async def test_stale_licence_review_blocks_dispatch(phase2_db, monkeypatch):
    monkeypatch.setattr(
        verification_service,
        "get_settings",
        lambda: SimpleNamespace(
            licence_class_map_reviewed=True,
            licence_class_map={"cab": ["LMV-TR"]},
            commercial_transport_endorsement_required={"cab": True},
            licence_revalidation_days=180,
        ),
    )
    async with phase2_db() as db:
        driver = User(phone="+14155552674", role=UserRole.DRIVER)
        db.add(driver)
        await db.flush()
        db.add(
            DriverProfile(
                user_id=driver.id,
                license_expiry=date(2035, 1, 1),
                vehicle_type="cab",
                vehicle_number="TEST-674",
                vehicle_model="Test model",
                vehicle_color="Blue",
                vehicle_year=2025,
                is_verified=True,
                verification_status="verified",
                is_online=False,
            )
        )
        db.add(
            DriverLicence(
                driver_id=driver.id,
                licence_number_enc="encrypted",
                licence_number_hmac="hmac",
                licence_last4="1234",
                holder_name_enc="encrypted",
                dob_enc="encrypted",
                vehicle_classes=["LMV-TR"],
                transport_endorsement=True,
                expiry_date=date(2035, 1, 1),
                status="approved",
                verification_source="parivahan",
                verification_reference="test-reference",
                verified_at=utc_now() - timedelta(days=181),
                reviewed_by=driver.id,
            )
        )
        await db.flush()
        eligible, reasons, _ = await verification_service.driver_eligibility(
            db, driver.id, "cab", require_online=False
        )
        assert not eligible
        assert "licence_revalidation_due" in reasons
