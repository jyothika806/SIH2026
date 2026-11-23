"""Fail-closed liveness endpoints and gated passenger OTP retrieval."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.core.database import get_db
from backend.app.api.core.security import AuthenticatedPrincipal, get_authenticated_principal
from backend.app.db.models import BiometricConsent, Ride
from backend.app.services.biometric_crypto import decrypt_text
from backend.app.services.verification_service import latest_valid_verification_attempt
from backend.app.services.utc_time import as_utc, utc_now

router = APIRouter(prefix="/liveness", tags=["Liveness Detection"])


class VerificationRequest(BaseModel):
    ride_id: int = Field(..., gt=0)


class DriverScanRequest(BaseModel):
    verification_id: str
    frame_data: str
    frame_format: str = "jpeg"


class BiometricFallbackRequest(BaseModel):
    verification_id: str
    auth_token: str
    biometric_method: str


def _verification_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Driver identity verification is unavailable; OTP remains locked",
    )


@router.get("/health")
async def health_check():
    return {
        "status": "unavailable",
        "verification": "disabled_until_authorized_face_model_is_configured",
    }


@router.post("/request-verification")
async def request_verification(
    request: VerificationRequest,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    raise _verification_unavailable()


@router.post("/verify-driver-scan")
async def verify_driver_scan(
    request: DriverScanRequest,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    raise _verification_unavailable()


@router.post("/biometric-fallback")
async def biometric_fallback(
    request: BiometricFallbackRequest,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    raise _verification_unavailable()


@router.get("/otp-status/{ride_id}")
async def get_otp_status(
    ride_id: int,
    response: Response,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.user_id
    if current_user.role != "passenger":
        raise HTTPException(status_code=403, detail="Only the passenger can retrieve this OTP")
    ride = await db.scalar(
        select(Ride).where(
            Ride.id == ride_id,
            Ride.passenger_id == user_id,
        )
    )
    if ride is None:
        raise HTTPException(status_code=404, detail="Ride not found")
    response.headers["Cache-Control"] = "no-store"

    consent_exists = await db.scalar(
        select(BiometricConsent.id)
        .where(
            BiometricConsent.driver_id == ride.driver_id,
            BiometricConsent.revoked_at.is_(None),
        )
        .with_for_update()
        .limit(1)
    )
    ride = await db.scalar(
        select(Ride)
        .where(
            Ride.id == ride_id,
            Ride.passenger_id == user_id,
        )
        .with_for_update()
    )
    if ride is None:
        raise HTTPException(status_code=404, detail="Ride not found")

    attempt = await latest_valid_verification_attempt(
        db, ride_id, ride.driver_id or 0
    )
    if (
        attempt is None
        or consent_exists is None
        or ride.status.value != "arrived"
        or not ride.otp_unlocked
        or not ride.otp
        or ride.otp_expires_at is None
        or as_utc(ride.otp_expires_at) <= utc_now()
        or ride.otp_consumed_at is not None
    ):
        return {
            "ride_id": ride_id,
            "otp_status": "locked",
            "verification_status": "pending",
            "otp_code": None,
            "otp_expires_at": None,
        }

    return {
        "ride_id": ride_id,
        "otp_status": "released",
        "verification_status": "success",
        "otp_code": decrypt_text(ride.otp),
        "otp_expires_at": ride.otp_expires_at,
    }


@router.delete("/sessions/{verification_id}")
async def cancel_verification_session(
    verification_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
):
    raise _verification_unavailable()
