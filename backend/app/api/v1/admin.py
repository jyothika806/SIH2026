"""Administrative driver verification endpoints."""

import hashlib
import hmac
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.core.config import get_settings
from backend.app.api.v1.core.database import get_db
from backend.app.api.core.security import AuthenticatedPrincipal, get_authenticated_principal
from backend.app.db.models import (
    DriverLicence,
    DriverProfile,
    FaceTemplate,
    User,
    UserRole,
    VerificationAuditLog,
)
from backend.app.services.biometric_crypto import encrypt_text
from backend.app.services.verification_service import driver_eligibility

router = APIRouter(prefix="/admin", tags=["Admin"])


class LicenceReviewRequest(BaseModel):
    licence_number: str = Field(..., min_length=5, max_length=50)
    holder_name: str = Field(..., min_length=2, max_length=120)
    date_of_birth: str = Field(..., min_length=8, max_length=10)
    vehicle_classes: list[str] = Field(default_factory=list)
    transport_endorsement: bool = False
    issue_date: date | None = None
    expiry_date: date
    outcome: Literal["pending", "approved", "rejected", "unavailable"]
    verification_reference: str = Field(..., min_length=1, max_length=255)
    rejection_reason: str | None = Field(None, max_length=500)


def _licence_hmac(value: str) -> str:
    key = get_settings().licence_hmac_key
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Licence verification storage is not configured",
        )
    return hmac.new(key.encode(), value.strip().upper().encode(), hashlib.sha256).hexdigest()


async def _require_admin(
    principal: AuthenticatedPrincipal, db: AsyncSession
) -> int:
    account = await db.scalar(select(User).where(User.id == principal.user_id))
    if account is None or not account.is_active or account.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return account.id


@router.put("/drivers/{driver_id}/licence")
async def review_driver_licence(
    driver_id: int,
    review: LicenceReviewRequest,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    reviewer_id = await _require_admin(current_user, db)
    profile = await db.scalar(
        select(DriverProfile).where(DriverProfile.user_id == driver_id)
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Driver profile not found")

    now = datetime.utcnow()
    status_value = review.outcome
    licence = DriverLicence(
        driver_id=driver_id,
        licence_number_enc=encrypt_text(review.licence_number),
        licence_number_hmac=_licence_hmac(review.licence_number),
        licence_last4=review.licence_number[-4:],
        holder_name_enc=encrypt_text(review.holder_name),
        dob_enc=encrypt_text(review.date_of_birth),
        vehicle_classes=[item.strip().upper() for item in review.vehicle_classes],
        transport_endorsement=review.transport_endorsement,
        issue_date=review.issue_date,
        expiry_date=review.expiry_date,
        status=status_value,
        verification_source="parivahan",
        verification_reference=review.verification_reference.strip(),
        verified_at=now,
        reviewed_by=reviewer_id,
        rejection_reason=review.rejection_reason,
    )
    db.add(licence)
    db.add(
        VerificationAuditLog(
            actor_id=reviewer_id,
            driver_id=driver_id,
            action="parivahan_licence_review",
            outcome=status_value,
            reason_code="review_completed",
            detail={
                "source": "parivahan",
                "reference": review.verification_reference.strip(),
            },
        )
    )
    profile.is_verified = False
    profile.verification_status = "pending"
    await db.flush()
    return {
        "driver_id": driver_id,
        "licence_status": status_value,
        "verification_source": "parivahan",
        "verification_reference": licence.verification_reference,
        "verified_at": now,
        "reviewed_by": reviewer_id,
        "dispatch_eligible": False,
    }


@router.post("/drivers/{driver_id}/templates/{template_id}/activate")
async def activate_face_template(
    driver_id: int,
    template_id: int,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    reviewer_id = await _require_admin(current_user, db)
    template = await db.scalar(
        select(FaceTemplate).where(
            FaceTemplate.id == template_id,
            FaceTemplate.driver_id == driver_id,
            FaceTemplate.status == "pending_review",
        )
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Pending face template not found")
    threshold = get_settings().face_enrollment_threshold
    if template.enrollment_score is None or template.enrollment_score < threshold:
        raise HTTPException(status_code=409, detail="Template does not meet the configured enrollment threshold")
    template.status = "active"
    template.activated_at = datetime.utcnow()
    db.add(
        VerificationAuditLog(
            actor_id=reviewer_id,
            driver_id=driver_id,
            action="face_template_activated",
            outcome="approved",
            reason_code="enrollment_threshold_met",
            detail={"template_id": template_id, "model_version": template.model_version},
        )
    )
    await db.flush()
    return {"driver_id": driver_id, "template_id": template_id, "status": "active"}


@router.post("/drivers/{driver_id}/approve-dispatch")
async def approve_driver_for_dispatch(
    driver_id: int,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    reviewer_id = await _require_admin(current_user, db)
    eligible, reasons, profile = await driver_eligibility(
        db,
        driver_id,
        require_online=False,
        require_profile_verified=False,
    )
    if not eligible or profile is None:
        raise HTTPException(
            status_code=409,
            detail={"message": "Driver re-verification is incomplete", "pending_checks": reasons},
        )
    profile.is_verified = True
    profile.verification_status = "verified"
    profile.verification_date = datetime.utcnow()
    db.add(
        VerificationAuditLog(
            actor_id=reviewer_id,
            driver_id=driver_id,
            action="driver_dispatch_approved",
            outcome="approved",
            reason_code="all_required_checks_passed",
            detail={},
        )
    )
    await db.flush()
    return {"driver_id": driver_id, "verification_status": "verified"}


@router.get("/drivers/{driver_id}/eligibility")
async def get_driver_eligibility(
    driver_id: int,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(current_user, db)
    eligible, reasons, _ = await driver_eligibility(
        db, driver_id, require_online=False
    )
    return {"driver_id": driver_id, "eligible": eligible, "pending_checks": reasons}
