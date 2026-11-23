"""
Driver Onboarding & Profile Management API

Endpoints:
- Create driver profile
- Upload documents
- Verify documents (admin)
- Update driver location
- Toggle online status
- Get driver profile
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum

from backend.app.api.core.security import AuthenticatedPrincipal, get_authenticated_principal
from backend.app.api.v1.core.database import get_db
from backend.app.db.models import (
    BiometricConsent,
    DriverProfile,
    DocumentVerification,
    FaceTemplate,
    Ride,
    User,
    VerificationAttempt,
    VerificationAuditLog,
)
from backend.app.api.v1.core.config import Settings
from backend.app.services.biometric_crypto import encrypt_text
from backend.app.services.verification_service import driver_eligibility
from backend.app.services.utc_time import utc_now

router = APIRouter(prefix="/driver", tags=["driver"])


class DocumentType(str, Enum):
    LICENSE = "license"
    VEHICLE_RC = "vehicle_rc"
    INSURANCE = "insurance"
    AADHAR = "aadhar"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DriverProfileCreate(BaseModel):
    license_number: str = Field(..., min_length=5, max_length=50)
    license_expiry: date
    vehicle_type: str = Field(..., pattern="^(bike|auto|cab)$")
    vehicle_number: str = Field(..., min_length=5, max_length=20)
    vehicle_model: str = Field(..., min_length=2, max_length=100)
    vehicle_color: str = Field(..., min_length=2, max_length=50)
    vehicle_year: int = Field(..., ge=2000, le=2030)


class DriverProfileResponse(BaseModel):
    id: int
    user_id: int
    license_number: str = Field(validation_alias="masked_license_number")
    license_expiry: date
    vehicle_type: str
    vehicle_number: str
    vehicle_model: str
    vehicle_color: str
    vehicle_year: int
    is_verified: bool
    verification_status: str
    total_rides: int
    total_earnings: float
    rating: float
    is_online: bool

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    id: int
    user_id: int
    document_type: str
    document_url: str
    verification_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class BiometricConsentRequest(BaseModel):
    granted: bool
    consent_text_version: str = Field(..., min_length=1, max_length=64)


@router.post("/biometric-consent")
async def record_biometric_consent(
    request: BiometricConsentRequest,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "driver":
        raise HTTPException(status_code=403, detail="Only drivers can manage consent")
    driver_id = current_user.user_id
    now = utc_now()
    existing = await db.scalars(
        select(BiometricConsent).where(
            BiometricConsent.driver_id == driver_id,
            BiometricConsent.revoked_at.is_(None),
        ).with_for_update()
    )
    for consent in existing:
        consent.revoked_at = now
    if not request.granted:
        await db.execute(
            update(VerificationAttempt)
            .where(
                VerificationAttempt.driver_id == driver_id,
                VerificationAttempt.status.in_(("pending", "success")),
            )
            .values(status="cancelled_consent_revoked")
        )
        await db.execute(
            update(Ride)
            .where(
                Ride.driver_id == driver_id,
                or_(
                    Ride.otp.is_not(None),
                    Ride.otp_hash.is_not(None),
                    Ride.otp_unlocked.is_(True),
                ),
            )
            .values(
                otp=None,
                otp_hash=None,
                otp_unlocked=False,
                otp_expires_at=None,
                otp_consumed_at=now,
            )
        )
        await db.execute(
            update(FaceTemplate)
            .where(
                FaceTemplate.driver_id == driver_id,
                FaceTemplate.status == "active",
            )
            .values(status="revoked_consent")
        )
    if request.granted:
        db.add(
            BiometricConsent(
                driver_id=driver_id,
                consent_text_version=request.consent_text_version,
                granted_at=now,
            )
        )
    db.add(
        VerificationAuditLog(
            actor_id=driver_id,
            driver_id=driver_id,
            action="biometric_consent",
            outcome="granted" if request.granted else "revoked",
            reason_code="driver_choice",
            detail={"consent_text_version": request.consent_text_version},
        )
    )
    await db.flush()
    return {"granted": request.granted, "recorded_at": now}


@router.post("/profile", response_model=DriverProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_driver_profile(
    profile_data: DriverProfileCreate,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new driver profile.
    
    Requires the user to be authenticated with role 'driver'.
    """
    if current_user.role != 'driver':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can create driver profiles"
        )
    
    user_id = current_user.user_id
    
    # Check if profile already exists
    existing_profile = await db.execute(
        select(DriverProfile).where(DriverProfile.user_id == user_id)
    )
    if existing_profile.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver profile already exists"
        )
    
    # Create driver profile
    driver_profile = DriverProfile(
        user_id=user_id,
        license_number=encrypt_text(profile_data.license_number),
        license_number_last4=profile_data.license_number[-4:],
        license_expiry=profile_data.license_expiry,
        vehicle_type=profile_data.vehicle_type,
        vehicle_number=profile_data.vehicle_number,
        vehicle_model=profile_data.vehicle_model,
        vehicle_color=profile_data.vehicle_color,
        vehicle_year=profile_data.vehicle_year,
        verification_status="pending"
    )
    
    db.add(driver_profile)
    await db.commit()
    await db.refresh(driver_profile)
    
    return driver_profile


@router.get("/profile", response_model=DriverProfileResponse)
async def get_driver_profile(
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current driver's profile.
    """
    user_id = current_user.user_id
    
    driver_profile = await db.execute(
        select(DriverProfile).where(DriverProfile.user_id == user_id)
    )
    profile = driver_profile.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    return profile


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    document_type: DocumentType,
    file: UploadFile = File(...),
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for verification.
    
    Supported document types: license, vehicle_rc, insurance, aadhar
    """
    if current_user.role != 'driver':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can upload documents"
        )
    
    user_id = current_user.user_id
    
    # In production, upload to S3/Cloud Storage and generate URL
    # For now, use a placeholder URL
    document_url = f"https://storage.optimalride.com/documents/{user_id}/{document_type.value}_{file.filename}"
    
    # Calculate document hash (placeholder - use actual hash in production)
    import hashlib
    content = await file.read()
    document_hash = hashlib.sha256(content).hexdigest()
    
    # Create document verification record
    document = DocumentVerification(
        user_id=user_id,
        document_type=document_type.value,
        document_url=document_url,
        document_hash=document_hash,
        verification_status="pending"
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    return document


@router.get("/documents")
async def get_documents(
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all documents uploaded by the current driver.
    """
    user_id = current_user.user_id
    
    documents = await db.execute(
        select(DocumentVerification).where(DocumentVerification.user_id == user_id)
    )
    docs = documents.scalars().all()
    
    return [
        {
            "id": doc.id,
            "document_type": doc.document_type,
            "document_url": doc.document_url,
            "verification_status": doc.verification_status,
            "verified_at": doc.verified_at,
            "rejection_reason": doc.rejection_reason,
            "created_at": doc.created_at
        }
        for doc in docs
    ]


@router.post("/location")
async def update_driver_location(
    location: LocationUpdate,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """
    Update driver's current location.
    """
    if current_user.role != 'driver':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can update location"
        )
    
    user_id = current_user.user_id
    
    # Update driver profile location
    from sqlalchemy import func
    from geoalchemy2 import functions as geofunc
    
    await db.execute(
        update(DriverProfile)
        .where(DriverProfile.user_id == user_id)
        .values(
            current_location=geofunc.ST_SetSRID(
                geofunc.ST_MakePoint(location.longitude, location.latitude),
                4326
            ),
            last_location_update=func.now()
        )
    )
    await db.commit()
    
    return {"success": True, "message": "Location updated successfully"}


@router.post("/online")
async def toggle_online_status(
    is_online: bool,
    current_user: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle driver's online status.
    """
    if current_user.role != 'driver':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can toggle online status"
        )
    
    user_id = current_user.user_id
    
    # Check if profile exists and is verified
    profile = await db.execute(
        select(DriverProfile).where(DriverProfile.user_id == user_id)
    )
    driver_profile = profile.scalar_one_or_none()
    
    if not driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found"
        )
    
    if is_online:
        eligible, reasons, _ = await driver_eligibility(
            db, user_id, require_online=False
        )
    else:
        eligible, reasons = True, []
    if not eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Driver verification is incomplete", "pending_checks": reasons}
        )
    
    # Update online status
    await db.execute(
        update(DriverProfile)
        .where(DriverProfile.user_id == user_id)
        .values(is_online=is_online)
    )
    await db.commit()
    
    return {"success": True, "is_online": is_online}


@router.get("/nearby")
async def get_nearby_drivers(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    vehicle_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get nearby available drivers within a radius.
    
    Uses PostGIS spatial query for efficient radius search.
    """
    from sqlalchemy import select, and_
    from geoalchemy2 import functions as geofunc
    
    # Build spatial query
    query = select(DriverProfile).where(
        and_(
            DriverProfile.is_online == True,
            DriverProfile.is_verified == True,
            geofunc.ST_DWithin(
                DriverProfile.current_location,
                geofunc.ST_SetSRID(
                    geofunc.ST_MakePoint(longitude, latitude),
                    4326
                ),
                radius_km * 1000  # Convert km to meters
            )
        )
    )
    
    if vehicle_type:
        query = query.where(DriverProfile.vehicle_type == vehicle_type)
    
    result = await db.execute(query)
    drivers = result.scalars().all()
    
    return [
        {
            "id": driver.id,
            "user_id": driver.user_id,
            "vehicle_type": driver.vehicle_type,
            "vehicle_number": driver.vehicle_number,
            "vehicle_model": driver.vehicle_model,
            "vehicle_color": driver.vehicle_color,
            "rating": driver.rating,
            "total_rides": driver.total_rides,
            "distance_km": float(
                await db.scalar(
                    select(
                        geofunc.ST_Distance(
                            driver.current_location,
                            geofunc.ST_SetSRID(
                                geofunc.ST_MakePoint(longitude, latitude),
                                4326
                            )
                        )
                    )
                ) / 1000
            )
        }
        for driver in drivers
    ]
