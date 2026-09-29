"""
Dynamic Fare Calculation & Split-Payment API Endpoints

This module implements:
- Fare calculation endpoint
- Fare estimation endpoint
- Split fare calculation endpoint
- Detour surcharge calculation endpoint

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional
from datetime import datetime

from backend.app.api.v1.auth import get_current_user
from backend.app.services.fare_service import fare_service, FareBreakdown, SplitFareAllocation, SurgeLevel
from backend.app.db.models import VehicleType

router = APIRouter(prefix="/fare", tags=["Fare & Payment"])


# Pydantic Schemas
class FareCalculationRequest(BaseModel):
    """Fare calculation request schema."""
    
    vehicle_type: Literal["bike", "auto", "cab"] = Field(..., description="Vehicle type")
    distance_km: float = Field(..., gt=0, description="Distance in kilometers")
    duration_minutes: float = Field(..., gt=0, description="Duration in minutes")
    surge_level: Literal["none", "low", "medium", "high", "extreme"] = Field("none", description="Surge level")
    detour_minutes: float = Field(0.0, ge=0, description="Detour time in minutes")
    apply_surge_cap: bool = Field(True, description="Whether to apply surge multiplier cap")


class FareCalculationResponse(BaseModel):
    """Fare calculation response schema."""
    
    base_fare: float = Field(..., description="Base fare")
    distance_fare: float = Field(..., description="Distance-based fare")
    time_fare: float = Field(..., description="Time-based fare")
    surge_multiplier: float = Field(..., description="Surge multiplier applied")
    surge_amount: float = Field(..., description="Surge amount added")
    detour_surcharge: float = Field(..., description="Detour surcharge")
    platform_fee: float = Field(..., description="Platform fee")
    subtotal: float = Field(..., description="Subtotal before platform fee")
    total_fare: float = Field(..., description="Total fare")
    currency: str = Field(..., description="Currency code")


class FareEstimateRequest(BaseModel):
    """Fare estimate request schema."""
    
    vehicle_type: Literal["bike", "auto", "cab"] = Field(..., description="Vehicle type")
    pickup_lat: float = Field(..., ge=-90, le=90, description="Pickup latitude")
    pickup_lon: float = Field(..., ge=-180, le=180, description="Pickup longitude")
    dropoff_lat: float = Field(..., ge=-90, le=90, description="Dropoff latitude")
    dropoff_lon: float = Field(..., ge=-180, le=180, description="Dropoff longitude")
    estimated_distance_km: Optional[float] = Field(None, gt=0, description="Estimated distance (optional)")
    estimated_duration_minutes: Optional[float] = Field(None, gt=0, description="Estimated duration (optional)")


class SplitFareRequest(BaseModel):
    """Split fare request schema."""
    
    total_fare: float = Field(..., gt=0, description="Total fare to split")
    passengers: List[Dict] = Field(..., description="List of passengers with id, name, and optional distance_share/share_percentage")
    split_method: Literal["equal", "distance", "custom"] = Field("equal", description="Split method")


class SplitFareResponse(BaseModel):
    """Split fare response schema."""
    
    total_fare: float = Field(..., description="Total fare")
    split_method: str = Field(..., description="Split method used")
    allocations: List[Dict] = Field(..., description="Fare allocations per passenger")


class DetourSurchargeRequest(BaseModel):
    """Detour surcharge request schema."""
    
    original_fare: float = Field(..., gt=0, description="Original fare without detour")
    detour_minutes: float = Field(..., ge=0, description="Detour time in minutes")
    num_passengers: int = Field(1, ge=1, description="Number of passengers to split surcharge")


# API Endpoints
@router.post("/calculate", response_model=FareCalculationResponse)
async def calculate_fare(
    request: FareCalculationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Calculate dynamic fare for a ride.
    
    Computes fare based on distance, time, vehicle type, surge level,
    and detour surcharge.
    
    Args:
        request: Fare calculation data
        current_user: Current user from JWT token
        
    Returns:
        FareCalculationResponse with detailed fare breakdown
    """
    try:
        # Convert string to enum
        vehicle_type = VehicleType(request.vehicle_type)
        surge_level = SurgeLevel(request.surge_level)
        
        # Calculate fare
        fare: FareBreakdown = fare_service.calculate_fare(
            vehicle_type=vehicle_type,
            distance_km=request.distance_km,
            duration_minutes=request.duration_minutes,
            surge_level=surge_level,
            detour_minutes=request.detour_minutes,
            apply_surge_cap=request.apply_surge_cap
        )
        
        return FareCalculationResponse(
            base_fare=fare.base_fare,
            distance_fare=fare.distance_fare,
            time_fare=fare.time_fare,
            surge_multiplier=fare.surge_multiplier,
            surge_amount=fare.surge_amount,
            detour_surcharge=fare.detour_surcharge,
            platform_fee=fare.platform_fee,
            subtotal=fare.subtotal,
            total_fare=fare.total_fare,
            currency=fare.currency
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fare calculation failed: {str(e)}"
        )


@router.post("/estimate")
async def estimate_fare(
    request: FareEstimateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get fare estimate for a route.
    
    Provides fare estimates with different surge levels for planning.
    
    Args:
        request: Fare estimate data
        current_user: Current user from JWT token
        
    Returns:
        Fare estimate with breakdown by surge level
    """
    try:
        vehicle_type = VehicleType(request.vehicle_type)
        
        # Calculate estimate
        estimate = fare_service.estimate_fare(
            vehicle_type=vehicle_type,
            pickup_lat=request.pickup_lat,
            pickup_lon=request.pickup_lon,
            dropoff_lat=request.dropoff_lat,
            dropoff_lon=request.dropoff_lon,
            estimated_distance_km=request.estimated_distance_km,
            estimated_duration_minutes=request.estimated_duration_minutes
        )
        
        return {
            "success": True,
            "estimate": estimate
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fare estimation failed: {str(e)}"
        )


@router.post("/split", response_model=SplitFareResponse)
async def split_fare(
    request: SplitFareRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Calculate fare split among passengers.
    
    Splits total fare among passengers using equal, distance-based,
    or custom percentage methods.
    
    Args:
        request: Split fare data
        current_user: Current user from JWT token
        
    Returns:
        SplitFareResponse with fare allocations
    """
    try:
        # Calculate split
        allocations: List[SplitFareAllocation] = fare_service.calculate_split_fare(
            total_fare=request.total_fare,
            passengers=request.passengers,
            split_method=request.split_method
        )
        
        return SplitFareResponse(
            total_fare=request.total_fare,
            split_method=request.split_method,
            allocations=[alloc.to_dict() for alloc in allocations]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fare split calculation failed: {str(e)}"
        )


@router.post("/detour-surcharge")
async def calculate_detour_surcharge(
    request: DetourSurchargeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Calculate detour surcharge for mid-route pickups.
    
    Computes additional fare for detours and distributes among passengers.
    
    Args:
        request: Detour surcharge data
        current_user: Current user from JWT token
        
    Returns:
        Detour surcharge breakdown
    """
    try:
        surcharge = fare_service.calculate_detour_surcharge(
            original_fare=request.original_fare,
            detour_minutes=request.detour_minutes,
            num_passengers=request.num_passengers
        )
        
        return {
            "success": True,
            "surcharge": surcharge
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detour surcharge calculation failed: {str(e)}"
        )


@router.get("/surge-level")
async def get_current_surge_level():
    """
    Get current surge level based on demand/supply.
    
    Returns:
        Current surge level information
    """
    try:
        # In production, this would calculate based on real demand/supply
        # For now, return default
        surge_level = fare_service.determine_surge_level(
            demand_factor=1.0,
            supply_factor=1.0,
            time_of_day=datetime.utcnow()
        )
        
        return {
            "current_level": surge_level.value,
            "multipliers": {
                level.value: multiplier 
                for level, multiplier in fare_service.surge_multipliers.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get surge level: {str(e)}"
        )
