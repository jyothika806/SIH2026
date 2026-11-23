"""Driver eligibility checks shared by dispatch and verification endpoints."""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.core.config import get_settings
from backend.app.db.models import (
    BiometricConsent,
    DriverLicence,
    DriverProfile,
    FaceTemplate,
    Ride,
    RideStatus,
    User,
    UserRole,
    VerificationAttempt,
    VerificationAuditLog,
)
from backend.app.services.biometric_crypto import encrypt_text
from backend.app.services.otp_service import generate_otp, hash_otp
from backend.app.services.utc_time import as_utc, utc_now


async def latest_valid_verification_attempt(
    db: AsyncSession,
    ride_id: int,
    driver_id: int,
    now: datetime | None = None,
) -> VerificationAttempt | None:
    now = as_utc(now) if now is not None else utc_now()
    return await db.scalar(
        select(VerificationAttempt)
        .join(FaceTemplate, VerificationAttempt.face_template_id == FaceTemplate.id)
        .where(
            VerificationAttempt.ride_id == ride_id,
            VerificationAttempt.driver_id == driver_id,
            VerificationAttempt.status == "success",
            VerificationAttempt.liveness_passed.is_(True),
            VerificationAttempt.match_score.is_not(None),
            VerificationAttempt.match_score >= get_settings().face_ride_threshold,
            VerificationAttempt.completed_at.is_not(None),
            VerificationAttempt.expires_at > now,
            FaceTemplate.driver_id == driver_id,
            FaceTemplate.status == "active",
            FaceTemplate.activated_at.is_not(None),
        )
        .order_by(VerificationAttempt.completed_at.desc())
    )


async def driver_eligibility(
    db: AsyncSession,
    driver_id: int,
    vehicle_type: str | None = None,
    require_online: bool = True,
    require_profile_verified: bool = True,
) -> tuple[bool, list[str], DriverProfile | None]:
    settings = get_settings()
    user = await db.scalar(select(User).where(User.id == driver_id))
    profile = await db.scalar(
        select(DriverProfile).where(DriverProfile.user_id == driver_id)
    )
    reasons: list[str] = []
    if user is None or user.role != UserRole.DRIVER or not user.is_active:
        return False, ["driver_account_unavailable"], profile
    if profile is None:
        return False, ["driver_profile_missing"], None
    if require_profile_verified and (
        not profile.is_verified or profile.verification_status != "verified"
    ):
        reasons.append("legacy_profile_pending")
    if require_online and not profile.is_online:
        reasons.append("driver_offline")

    licences = await db.scalars(
        select(DriverLicence)
        .where(DriverLicence.driver_id == driver_id)
        .order_by(DriverLicence.created_at.desc())
    )
    licence = licences.first()
    if licence is None:
        reasons.append(
            "licence_pending" if profile.license_number_last4 else "licence_unavailable"
        )
    elif licence.status != "approved":
        reasons.append(f"licence_{licence.status}")
    elif licence.verification_source != "parivahan":
        reasons.append("licence_source_unapproved")
    elif (
        not licence.verification_source
        or not licence.verification_reference
        or not licence.verified_at
        or not licence.reviewed_by
    ):
        reasons.append("licence_evidence_incomplete")
    elif licence.expiry_date <= date.today():
        reasons.append("licence_expired")
    elif (
        licence.verified_at is not None
        and as_utc(licence.verified_at)
        < utc_now() - timedelta(days=settings.licence_revalidation_days)
    ):
        reasons.append("licence_revalidation_due")
    elif not settings.licence_class_map_reviewed:
        reasons.append("licence_class_mapping_unreviewed")
    else:
        required_classes = settings.licence_class_map.get(
            vehicle_type or profile.vehicle_type, []
        )
        if not required_classes:
            reasons.append("vehicle_class_mapping_unavailable")
        elif not set(licence.vehicle_classes).intersection(required_classes):
            reasons.append("vehicle_class_mismatch")
        elif settings.commercial_transport_endorsement_required.get(
            vehicle_type or profile.vehicle_type, True
        ) and not licence.transport_endorsement:
            reasons.append("transport_endorsement_missing")

    consent = await db.scalar(
        select(BiometricConsent.id)
        .where(
            BiometricConsent.driver_id == driver_id,
            BiometricConsent.revoked_at.is_(None),
        )
        .limit(1)
    )
    if consent is None:
        reasons.append("biometric_consent_missing")

    template = await db.scalar(
        select(FaceTemplate.id)
        .where(
            FaceTemplate.driver_id == driver_id,
            FaceTemplate.status == "active",
            FaceTemplate.activated_at.is_not(None),
        )
        .limit(1)
    )
    if template is None:
        reasons.append("face_template_unavailable")

    return not reasons, reasons, profile


async def release_ride_otp(
    db: AsyncSession,
    ride: Ride,
    attempt: VerificationAttempt,
) -> str:
    """Release OTP only after a trusted server-side identity/liveness result."""
    settings = get_settings()
    now = utc_now()
    consent = await db.scalar(
        select(BiometricConsent.id)
        .where(
            BiometricConsent.driver_id == attempt.driver_id,
            BiometricConsent.revoked_at.is_(None),
        )
        .with_for_update()
        .limit(1)
    )
    eligible, _, _ = await driver_eligibility(
        db, attempt.driver_id, ride.vehicle_type.value, require_online=False
    )
    template = await db.scalar(
        select(FaceTemplate).where(
            FaceTemplate.id == attempt.face_template_id,
            FaceTemplate.driver_id == ride.driver_id,
            FaceTemplate.status == "active",
            FaceTemplate.activated_at.is_not(None),
        )
    )
    if (
        ride.status != RideStatus.ARRIVED
        or ride.driver_id != attempt.driver_id
        or not eligible
        or consent is None
        or attempt.ride_id != ride.id
        or attempt.status != "success"
        or not attempt.liveness_passed
        or attempt.match_score is None
        or attempt.match_score < settings.face_ride_threshold
        or attempt.completed_at is None
        or as_utc(attempt.expires_at) <= now
        or template is None
        or ride.otp_consumed_at is not None
        or (
            ride.otp is not None
            and ride.otp_expires_at is not None
            and as_utc(ride.otp_expires_at) > now
        )
    ):
        raise ValueError("A successful live identity verification is required")
    code = generate_otp()
    ride.otp = encrypt_text(code)
    ride.otp_hash = hash_otp(code, "ride-start", str(ride.id))
    ride.otp_unlocked = True
    ride.otp_expires_at = now + timedelta(minutes=settings.trip_otp_expire_minutes)
    db.add(
        VerificationAuditLog(
            actor_id=attempt.driver_id,
            driver_id=attempt.driver_id,
            ride_id=ride.id,
            action="ride_otp_released",
            outcome="success",
            reason_code="identity_and_liveness_verified",
            detail={"verification_attempt_id": attempt.id},
        )
    )
    await db.flush()
    return code
