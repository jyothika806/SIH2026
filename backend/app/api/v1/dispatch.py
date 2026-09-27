"""
Driver Dispatch API Endpoints

Endpoints:
- Find available drivers (radius-based)
- Dispatch ride to driver
- Accept ride
- Reject ride
- Auto-dispatch with timeout
- Get driver queue
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List

from ..core.security import get_current_user
from ..db.database import get_db
from ..services.dispatch_service import dispatch_service

router = APIRouter(prefix="/dispatch", tags=["Dispatch"])


class DriverSearchRequest(BaseModel):
    pickup_lat: float = Field(..., ge=-90, le=90)
    pickup_lon: float = Field(..., ge=-180, le=180)
    vehicle_type: Optional[str] = None
    radius_km: Optional[float] = Field(None, ge=0.1, le=50)


class DispatchRequest(BaseModel):
    ride_id: int = Field(..., gt=0)
    driver_id: int = Field(..., gt=0)


class AcceptRideRequest(BaseModel):
    ride_id: int = Field(..., gt=0)


class RejectRideRequest(BaseModel):
    ride_id: int = Field(..., gt=0)
    reason: Optional[str] = None


@router.post("/drivers/nearby")
async def find_nearby_drivers(
    request: DriverSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Find available drivers within a radius using PostGIS spatial query.
    
    Returns drivers sorted by distance (closest first).
    """
    drivers = await dispatch_service.find_available_drivers(
        db,
        request.pickup_lat,
        request.pickup_lon,
        request.vehicle_type,
        request.radius_km
    )
    
    return {
        "success": True,
        "pickup_location": {
            "latitude": request.pickup_lat,
            "longitude": request.pickup_lon
        },
        "search_radius_km": request.radius_km or 5.0,
        "vehicle_type_filter": request.vehicle_type,
        "drivers_found": len(drivers),
        "drivers": drivers
    }


@router.post("/dispatch")
async def dispatch_ride(
    request: DispatchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Dispatch a ride to a specific driver.
    
    Requires admin or system-level authentication.
    """
    if current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can dispatch rides"
        )
    
    result = await dispatch_service.dispatch_ride_to_driver(
        db,
        request.ride_id,
        request.driver_id
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.post("/accept")
async def accept_ride(
    request: AcceptRideRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Driver accepts a dispatched ride.
    
    Requires driver authentication.
    """
    if current_user.get('role') != 'driver':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can accept rides"
        )
    
    driver_id = current_user.get('id')
    
    result = await dispatch_service.accept_ride(
        db,
        request.ride_id,
        driver_id
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.post("/reject")
async def reject_ride(
    request: RejectRideRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Driver rejects a dispatched ride.
    
    Requires driver authentication.
    """
    if current_user.get('role') != 'driver':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can reject rides"
        )
    
    driver_id = current_user.get('id')
    
    result = await dispatch_service.reject_ride(
        db,
        request.ride_id,
        driver_id,
        request.reason
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.post("/auto-dispatch")
async def auto_dispatch(
    ride_id: int,
    pickup_lat: float,
    pickup_lon: float,
    vehicle_type: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-dispatch ride with timeout handling.
    
    Finds available drivers and dispatches to closest.
    Requires admin or system-level authentication.
    """
    if current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can auto-dispatch rides"
        )
    
    result = await dispatch_service.auto_dispatch_with_timeout(
        db,
        ride_id,
        pickup_lat,
        pickup_lon,
        vehicle_type
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.get("/queue/{driver_id}")
async def get_driver_queue(
    driver_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get ride requests in queue for a specific driver.
    
    Returns nearby rides in requested/searching state.
    """
    if current_user.get('role') != 'driver' or current_user.get('id') != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    queue = await dispatch_service.get_driver_queue(db, driver_id)
    
    return {
        "success": True,
        "driver_id": driver_id,
        "queue_size": len(queue),
        "queue": queue
    }
