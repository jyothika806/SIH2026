import asyncio
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from backend.app.api.v1.liveness import VerificationRequest, get_otp_status, request_verification
from backend.app.api.core.security import AuthenticatedPrincipal
from backend.app.api.v1.rides import RideStartRequest, start_ride
from backend.app.db.models import (
    BiometricConsent,
    DriverProfile,
    FaceTemplate,
    Ride,
    RideStatus,
    SeatReservation,
    User,
    UserRole,
    VehicleType,
    VerificationAttempt,
)
from backend.app.services import reservation_service, verification_service
from backend.app.services import biometric_crypto
from backend.app.services.biometric_crypto import encrypt_text
from backend.app.services import otp_service
from backend.app.services.otp_service import hash_otp
from backend.app.services.utc_time import utc_now


TEST_SETTINGS = SimpleNamespace(
    licence_class_map_reviewed=True,
    licence_class_map={"cab": ["LMV-TR"]},
    commercial_transport_endorsement_required={"cab": True},
    vehicle_capacities={"cab": 4},
    seat_hold_ttl_seconds=60,
    face_ride_threshold=0.363,
    face_enrollment_threshold=0.363,
    trip_otp_expire_minutes=5,
    fernet_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    otp_hmac_key="test-key-that-is-at-least-thirty-two-characters",
)


@pytest.fixture(autouse=True)
def use_test_settings(monkeypatch):
    monkeypatch.setattr(reservation_service, "get_settings", lambda: TEST_SETTINGS)
    monkeypatch.setattr(verification_service, "get_settings", lambda: TEST_SETTINGS)
    monkeypatch.setattr(biometric_crypto, "get_settings", lambda: TEST_SETTINGS)
    monkeypatch.setattr(otp_service.settings, "otp_hmac_key", TEST_SETTINGS.otp_hmac_key)


async def seed_driver_and_ride(db, *, search_expires_at: datetime):
    passenger = User(phone="+15550000001", role=UserRole.PASSENGER, is_active=True)
    driver = User(phone="+15550000002", role=UserRole.DRIVER, is_active=True)
    db.add_all([passenger, driver])
    await db.flush()
    profile = DriverProfile(
        user_id=driver.id,
        vehicle_type="cab",
        vehicle_number=f"TEST-{driver.id}",
        license_expiry=date(2035, 1, 1),
        vehicle_model="Test model",
        vehicle_color="Blue",
        vehicle_year=2025,
        is_verified=False,
        verification_status="pending",
        is_online=True,
    )
    db.add(profile)
    template = FaceTemplate(
        driver_id=driver.id,
        encrypted_embedding=b"unavailable",
        model_version="not-configured",
        status="pending_review",
    )
    db.add(template)
    ride = Ride(
        passenger_id=passenger.id,
        vehicle_type=VehicleType.CAB,
        pickup_point=WKTElement("POINT(77.5946 12.9716)", srid=4326),
        dropoff_point=WKTElement("POINT(77.6245 12.9352)", srid=4326),
        seats_total=4,
        seats_occupied=1,
        seats_required=1,
        status=RideStatus.SEARCHING,
        search_expires_at=search_expires_at,
    )
    db.add(ride)
    await db.flush()
    return passenger, driver, profile, template, ride


def allow_dispatch_for_lifecycle_test(monkeypatch, profile):
    async def eligible(*args, **kwargs):
        return True, [], profile

    monkeypatch.setattr(reservation_service, "driver_eligibility", eligible)


@pytest.mark.asyncio
async def test_expired_driver_hold_releases_driver_without_cancelling_booking(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        now = utc_now()
        _, driver, profile, _, ride = await seed_driver_and_ride(
            db, search_expires_at=now + timedelta(minutes=10)
        )
        allow_dispatch_for_lifecycle_test(monkeypatch, profile)
        assigned, _ = await reservation_service.assign_driver_with_hold(
            db, ride.id, driver.id, now
        )
        assert assigned
        await db.commit()

        result = await reservation_service.sweep_expired_lifecycle(
            db, now + timedelta(seconds=60)
        )
        accepted, _ = await reservation_service.accept_driver_hold(
            db, ride.id, driver.id, now + timedelta(seconds=60)
        )
        await db.refresh(ride)
        reservation = await db.scalar(
            select(SeatReservation).where(SeatReservation.ride_id == ride.id)
        )
        assert result["holds_released"] == 1
        assert reservation.status == "expired"
        assert not accepted
        assert ride.status == RideStatus.SEARCHING
        assert ride.driver_id is None


@pytest.mark.asyncio
async def test_acceptance_and_hold_expiry_are_linearized(phase2_db, monkeypatch):
    async with phase2_db() as db:
        now = utc_now()
        _, driver, profile, _, ride = await seed_driver_and_ride(
            db, search_expires_at=now + timedelta(minutes=10)
        )
        allow_dispatch_for_lifecycle_test(monkeypatch, profile)
        assigned, _ = await reservation_service.assign_driver_with_hold(
            db, ride.id, driver.id, now
        )
        assert assigned
        await db.commit()

        accepted, _ = await reservation_service.accept_driver_hold(
            db, ride.id, driver.id, now + timedelta(seconds=59)
        )
        assert accepted
        await db.commit()
        await reservation_service.sweep_expired_lifecycle(
            db, now + timedelta(seconds=60)
        )
        await db.refresh(ride)
        reservation = await db.scalar(
            select(SeatReservation).where(SeatReservation.ride_id == ride.id)
        )
        assert ride.status == RideStatus.ARRIVED
        assert reservation.status == "confirmed"


@pytest.mark.asyncio
async def test_acceptance_racing_hold_expiry_keeps_booking_consistent(
    phase2_db, monkeypatch
):
    async with phase2_db() as setup:
        now = utc_now()
        _, driver, profile, _, ride = await seed_driver_and_ride(
            setup, search_expires_at=now + timedelta(minutes=10)
        )
        allow_dispatch_for_lifecycle_test(monkeypatch, profile)
        assigned, _ = await reservation_service.assign_driver_with_hold(
            setup, ride.id, driver.id, now
        )
        assert assigned
        await setup.commit()
        ride_id, driver_id = ride.id, driver.id

    ready_count = 0
    ready = asyncio.Event()

    async def synchronize():
        nonlocal ready_count
        ready_count += 1
        if ready_count == 2:
            ready.set()
        await ready.wait()

    async def accept():
        async with phase2_db() as db:
            await synchronize()
            result = await reservation_service.accept_driver_hold(
                db, ride_id, driver_id, now + timedelta(seconds=59)
            )
            await db.commit()
            return result[0]

    async def expire():
        async with phase2_db() as db:
            await synchronize()
            result = await reservation_service.sweep_expired_lifecycle(
                db, now + timedelta(seconds=60)
            )
            await db.commit()
            return result

    accepted, expiry = await asyncio.wait_for(
        asyncio.gather(accept(), expire()), timeout=5
    )
    async with phase2_db() as db:
        ride = await db.get(Ride, ride_id)
        reservation = await db.scalar(
            select(SeatReservation).where(SeatReservation.ride_id == ride_id)
        )
        assert expiry["holds_released"] in {0, 1}
        if accepted:
            assert ride.status == RideStatus.ARRIVED
            assert reservation.status == "confirmed"
        else:
            assert ride.status == RideStatus.SEARCHING
            assert reservation.status == "expired"
        assert ride.passenger_id is not None


@pytest.mark.asyncio
async def test_booking_search_expiry_wins_against_late_acceptance(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        now = utc_now()
        deadline = now + timedelta(seconds=30)
        _, driver, profile, _, ride = await seed_driver_and_ride(
            db, search_expires_at=deadline
        )
        allow_dispatch_for_lifecycle_test(monkeypatch, profile)
        assigned, _ = await reservation_service.assign_driver_with_hold(
            db, ride.id, driver.id, now
        )
        assert assigned
        await db.commit()

        accepted, _ = await reservation_service.accept_driver_hold(
            db, ride.id, driver.id, deadline
        )
        assert not accepted
        await reservation_service.sweep_expired_lifecycle(db, deadline)
        await db.refresh(ride)
        reservation = await db.scalar(
            select(SeatReservation).where(SeatReservation.ride_id == ride.id)
        )
        assert ride.status == RideStatus.NO_DRIVER_FOUND
        assert ride.driver_id is None
        assert reservation.status == "expired"
        assert reservation.reason == "booking_search_expired"


@pytest.mark.asyncio
async def test_existing_unverified_driver_is_not_eligible_for_dispatch(phase2_db):
    async with phase2_db() as db:
        now = utc_now()
        _, driver, profile, _, ride = await seed_driver_and_ride(
            db, search_expires_at=now + timedelta(minutes=10)
        )
        profile.license_number = "encrypted-legacy-value"
        profile.license_number_last4 = "1234"

        eligible, reasons, _ = await verification_service.driver_eligibility(
            db, driver.id, vehicle_type=ride.vehicle_type.value, require_online=False
        )

        assert not eligible
        assert "legacy_profile_pending" in reasons
        assert "licence_pending" in reasons
        assert "biometric_consent_missing" in reasons
        assert "face_template_unavailable" in reasons


@pytest.mark.asyncio
async def test_successful_acceptance_survives_booking_search_expiry(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        now = utc_now()
        deadline = now + timedelta(seconds=30)
        _, driver, profile, _, ride = await seed_driver_and_ride(
            db, search_expires_at=deadline
        )
        allow_dispatch_for_lifecycle_test(monkeypatch, profile)
        assigned, _ = await reservation_service.assign_driver_with_hold(
            db, ride.id, driver.id, now
        )
        assert assigned
        await db.commit()
        accepted, _ = await reservation_service.accept_driver_hold(
            db, ride.id, driver.id, deadline - timedelta(seconds=1)
        )
        assert accepted
        await db.commit()

        await reservation_service.sweep_expired_lifecycle(db, deadline)
        await db.refresh(ride)
        assert ride.status == RideStatus.ARRIVED
        assert ride.driver_id == driver.id


@pytest.mark.asyncio
async def test_verification_request_fails_closed_without_authorized_model():
    with pytest.raises(HTTPException) as verification_error:
        await request_verification(VerificationRequest(ride_id=1), {}, None)

    assert verification_error.value.status_code == 503


@pytest.mark.asyncio
async def test_unverified_attempt_cannot_expose_or_start_with_persisted_otp(
    phase2_db, monkeypatch
):
    async with phase2_db() as db:
        now = utc_now()
        passenger, driver, profile, template, ride = await seed_driver_and_ride(
            db, search_expires_at=now + timedelta(minutes=10)
        )
        allow_dispatch_for_lifecycle_test(monkeypatch, profile)
        assigned, _ = await reservation_service.assign_driver_with_hold(
            db, ride.id, driver.id, now
        )
        assert assigned
        accepted, _ = await reservation_service.accept_driver_hold(
            db, ride.id, driver.id, now + timedelta(seconds=1)
        )
        assert accepted
        attempt = VerificationAttempt(
            ride_id=ride.id,
            driver_id=driver.id,
            face_template_id=template.id,
            nonce_hash="nonce-hash",
            status="pending",
            liveness_passed=False,
            expires_at=now + timedelta(minutes=5),
        )
        db.add(attempt)
        db.add(
            BiometricConsent(
                driver_id=driver.id,
                consent_text_version="test-v1",
                granted_at=now,
            )
        )
        code = "123456"
        ride.otp = encrypt_text(code)
        ride.otp_hash = hash_otp(code, "ride-start", str(ride.id))
        ride.otp_unlocked = True
        ride.otp_expires_at = now + timedelta(minutes=5)
        await db.flush()

        with pytest.raises(ValueError, match="successful live identity verification"):
            await verification_service.release_ride_otp(db, ride, attempt)

        otp_status = await get_otp_status(
            ride.id,
            Response(),
            AuthenticatedPrincipal(
                user_id=passenger.id, role="passenger", phone=passenger.phone
            ),
            db,
        )
        assert otp_status["otp_status"] == "locked"
        assert otp_status["otp_code"] is None

        async def eligible(*args, **kwargs):
            return True, [], None

        monkeypatch.setattr("backend.app.api.v1.rides.driver_eligibility", eligible)
        with pytest.raises(HTTPException) as start_error:
            await start_ride(
                ride.id,
                RideStartRequest(otp="123456"),
                AuthenticatedPrincipal(
                    user_id=driver.id, role="driver", phone=driver.phone
                ),
                db,
            )
        assert start_error.value.status_code == 403
        assert start_error.value.detail == "Driver identity verification is incomplete"
