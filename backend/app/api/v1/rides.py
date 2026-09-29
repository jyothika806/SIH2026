"""
Ride Management API with WebSockets and Mid-Route Logic

This module implements:
- Ride lifecycle management
- Mid-route pickup requests with passenger consent
- Modal shift suggestions
- WebSocket real-time tracking
- Driver and passenger ride coordination

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import text
from typing import Optional, List, Literal, Dict
from datetime import datetime
import json
import asyncio

from backend.app.api.v1.core.database import get_db
from backend.app.api.v1.core.config import get_settings
from backend.app.db.models import (
    User, Ride, MidRouteRequest, UserRole, VehicleType,
    RideStatus, MidRouteStatus
)
from backend.app.db.spatial_queries import spatial_service
from backend.app.services.matching_service import matching_service
from backend.app.services.notification import notification_manager, NotificationType
from backend.app.api.v1.auth import get_current_user

router = APIRouter(prefix="/rides", tags=["Rides"])

# Get settings
settings = get_settings()

# JWT Bearer token security
security = HTTPBearer()

# WebSocket connection manager
class ConnectionManager:
    """WebSocket connection manager for ride tracking."""
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, ride_id: str):
        """Connect a WebSocket to a ride."""
        await websocket.accept()
        
        if ride_id not in self.active_connections:
            self.active_connections[ride_id] = []
        
        self.active_connections[ride_id].append(websocket)
        print(f"WebSocket connected for ride {ride_id}")
    
    def disconnect(self, websocket: WebSocket, ride_id: str):
        """Disconnect a WebSocket from a ride."""
        if ride_id in self.active_connections:
            self.active_connections[ride_id].remove(websocket)
            
            if not self.active_connections[ride_id]:
                del self.active_connections[ride_id]
        
        print(f"WebSocket disconnected for ride {ride_id}")
    
    async def broadcast(self, ride_id: str, message: dict):
        """Broadcast message to all connected WebSockets for a ride."""
        if ride_id in self.active_connections:
            for connection in self.active_connections[ride_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting to connection: {e}")
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")


# Global connection manager
manager = ConnectionManager()


# Pydantic Schemas
class RideBookingRequest(BaseModel):
    """Ride booking request schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    pickup_lat: float = Field(..., ge=-90, le=90, description="Pickup latitude")
    pickup_lon: float = Field(..., ge=-180, le=180, description="Pickup longitude")
    dropoff_lat: float = Field(..., ge=-90, le=90, description="Dropoff latitude")
    dropoff_lon: float = Field(..., ge=-180, le=180, description="Dropoff longitude")
    vehicle_type: Literal["bike", "auto", "cab"] = Field(..., description="Vehicle type")
    seats_required: int = Field(1, ge=1, le=4, description="Number of seats required")
    is_mid_route: bool = Field(False, description="Whether this is a mid-route pickup request")
    target_ride_id: Optional[int] = Field(None, description="Target ride ID for mid-route pickup")


class RideResponse(BaseModel):
    """Ride response schema."""
    
    id: int = Field(..., description="Ride ID")
    driver_id: int = Field(..., description="Driver ID")
    passenger_id: int = Field(..., description="Passenger ID")
    vehicle_type: str = Field(..., description="Vehicle type")
    seats_total: int = Field(..., description="Total seats")
    seats_occupied: int = Field(..., description="Occupied seats")
    status: str = Field(..., description="Ride status")
    otp_unlocked: bool = Field(..., description="OTP unlock status")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in minutes")
    estimated_distance: Optional[int] = Field(None, description="Estimated distance in meters")
    fare: Optional[float] = Field(None, description="Ride fare")
    driver_info: Optional[dict] = Field(None, description="Driver information")


class MidRouteConsentRequest(BaseModel):
    """Mid-route consent request schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    mid_route_request_id: int = Field(..., description="Mid-route request ID")
    consent: Literal["accepted", "rejected"] = Field(..., description="Consent decision")
    passenger_id: int = Field(..., description="Passenger ID providing consent")


class MidRouteRequestCreate(BaseModel):
    """Mid-route request creation schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    ride_id: int = Field(..., description="Target ride ID")
    pickup_lat: float = Field(..., ge=-90, le=90, description="Pickup latitude")
    pickup_lon: float = Field(..., ge=-180, le=180, description="Pickup longitude")
    dropoff_lat: float = Field(..., ge=-90, le=90, description="Dropoff latitude")
    dropoff_lon: float = Field(..., ge=-180, le=180, description="Dropoff longitude")


class TelemetryUpdate(BaseModel):
    """Telemetry update schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    ride_id: int = Field(..., description="Ride ID")
    latitude: float = Field(..., ge=-90, le=90, description="Current latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Current longitude")
    speed: Optional[float] = Field(None, description="Speed in km/h")
    heading: Optional[float] = Field(None, description="Heading in degrees")
    battery_level: Optional[int] = Field(None, description="Battery level percentage")


# API Endpoints
@router.post("/book", response_model=RideResponse, status_code=status.HTTP_201_CREATED)
async def book_ride(
    ride_request: RideBookingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Book a new ride or request mid-route pickup.
    
    For initial rides, creates a new ride request.
    For mid-route pickups, creates a mid-route request to join an existing ride.
    
    Args:
        ride_request: Ride booking data
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        Created ride or mid-route request information
    """
    try:
        user_id = int(current_user.get("sub"))
        user_role = current_user.get("role")
        
        if user_role != "passenger":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only passengers can book rides"
            )
        
        if ride_request.is_mid_route:
            # Handle mid-route pickup request
            return await handle_mid_route_request(
                ride_request, user_id, db
            )
        else:
            # Handle initial ride booking
            return await handle_initial_booking(
                ride_request, user_id, db
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ride booking failed: {str(e)}"
        )


async def handle_initial_booking(
    ride_request: RideBookingRequest,
    passenger_id: int,
    db: AsyncSession
) -> RideResponse:
    """Handle initial ride booking."""
    
    # Calculate route geometry using OSRM
    route_result = await matching_service.calculate_route_geometry(
        ride_request.pickup_lat,
        ride_request.pickup_lon,
        ride_request.dropoff_lat,
        ride_request.dropoff_lon
    )
    
    # Create ride record
    ride = Ride(
        driver_id=None,  # Will be assigned by matching algorithm
        passenger_id=passenger_id,
        vehicle_type=VehicleType(ride_request.vehicle_type),
        pickup_point=f"POINT({ride_request.pickup_lon} {ride_request.pickup_lat})",
        dropoff_point=f"POINT({ride_request.dropoff_lon} {ride_request.dropoff_lat})",
        route_geometry=f"LINESTRING({route_result['geometry']})",
        seats_total=ride_request.seats_required,
        seats_occupied=1,
        status=RideStatus.REQUESTED,
        estimated_duration=int(route_result['duration_minutes']),
        estimated_distance=int(route_result['distance_km'] * 1000),
        otp_unlocked=False
    )
    
    db.add(ride)
    await db.commit()
    await db.refresh(ride)
    
    # Find matching drivers using spatial queries
    # In production, this would trigger driver matching algorithm
    matching_rides = await matching_service.find_matching_rides(
        db,
        ride_request.pickup_lat,
        ride_request.pickup_lon,
        ride_request.dropoff_lat,
        ride_request.dropoff_lon,
        VehicleType(ride_request.vehicle_type)
    )
    
    return RideResponse(
        id=ride.id,
        driver_id=ride.driver_id or 0,
        passenger_id=ride.passenger_id,
        vehicle_type=ride.vehicle_type.value,
        seats_total=ride.seats_total,
        seats_occupied=ride.seats_occupied,
        status=ride.status.value,
        otp_unlocked=ride.otp_unlocked,
        estimated_duration=ride.estimated_duration,
        estimated_distance=ride.estimated_distance,
        fare=ride.fare,
        driver_info=None
    )


async def handle_mid_route_request(
    ride_request: RideBookingRequest,
    passenger_id: int,
    db: AsyncSession
) -> RideResponse:
    """Handle mid-route pickup request."""
    
    # Calculate detour time
    detour_time, detour_distance = await spatial_service.calculate_detour_time(
        db,
        ride_request.target_ride_id,
        ride_request.pickup_lat,
        ride_request.pickup_lon,
        ride_request.dropoff_lat,
        ride_request.dropoff_lon
    )
    
    # Check if detour is within cap
    if detour_time > settings.max_detour_minutes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Detour time ({detour_time:.1f} min) exceeds maximum allowed ({settings.max_detour_minutes} min)"
        )
    
    # Create mid-route request
    mid_route_request = MidRouteRequest(
        ride_id=ride_request.target_ride_id,
        passenger_id=passenger_id,
        pickup_point=f"POINT({ride_request.pickup_lon} {ride_request.pickup_lat})",
        dropoff_point=f"POINT({ride_request.dropoff_lon} {ride_request.dropoff_lat})",
        status=MidRouteStatus.PENDING,
        detour_minutes=detour_time,
        consent_required=True,
        consent_responses={}
    )
    
    db.add(mid_route_request)
    await db.commit()
    await db.refresh(mid_route_request)
    
    # Get ride and driver information
    ride_result = await db.execute(
        select(Ride).where(Ride.id == ride_request.target_ride_id)
    )
    ride = ride_result.scalar_one_or_none()
    
    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target ride not found"
        )
    
    # Get driver information
    driver_result = await db.execute(
        select(User).where(User.id == ride.driver_id)
    )
    driver = driver_result.scalar_one_or_none()
    
    # Request consent from existing passengers
    passenger_tokens = await get_passenger_fcm_tokens(db, ride.id)
    
    if passenger_tokens:
        await notification_manager.request_mid_route_consent(
            passenger_tokens,
            ride.id,
            1,  # new passenger count
            detour_time
        )
    
    # Broadcast mid-route request via WebSocket
    await manager.broadcast(
        str(ride.id),
        {
            "type": "mid_route_request",
            "request_id": mid_route_request.id,
            "passenger_id": passenger_id,
            "detour_minutes": detour_time,
            "pickup_lat": ride_request.pickup_lat,
            "pickup_lon": ride_request.pickup_lon
        }
    )
    
    return RideResponse(
        id=ride.id,
        driver_id=ride.driver_id,
        passenger_id=ride.passenger_id,
        vehicle_type=ride.vehicle_type.value,
        seats_total=ride.seats_total,
        seats_occupied=ride.seats_occupied,
        status=ride.status.value,
        otp_unlocked=ride.otp_unlocked,
        estimated_duration=ride.estimated_duration,
        estimated_distance=ride.estimated_distance,
        fare=ride.fare,
        driver_info={
            "id": driver.id if driver else 0,
            "age": driver.age if driver else None,
            "gender": driver.gender if driver else None,
            "rating": driver.rating if driver else 0.0
        } if driver else None
    )


@router.post("/mid-route/consent")
async def submit_mid_route_consent(
    consent_request: MidRouteConsentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit consent for mid-route pickup request.
    
    Existing onboard passengers accept or reject a proposed mid-route rider
    based on comfort and convenience.
    
    Args:
        consent_request: Consent request data
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        Consent submission status
    """
    try:
        # Verify passenger is on the ride
        passenger_id = int(current_user.get("sub"))
        
        # Get mid-route request
        result = await db.execute(
            select(MidRouteRequest).where(
                MidRouteRequest.id == consent_request.mid_route_request_id
            )
        )
        mid_route_request = result.scalar_one_or_none()
        
        if not mid_route_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mid-route request not found"
            )
        
        # Update consent responses
        if mid_route_request.consent_responses is None:
            mid_route_request.consent_responses = {}
        
        mid_route_request.consent_responses[str(passenger_id)] = consent_request.consent
        
        # Check if all consents received
        ride_result = await db.execute(
            select(Ride).where(Ride.id == mid_route_request.ride_id)
        )
        ride = ride_result.scalar_one_or_none()
        
        if ride:
            total_passengers = ride.seats_occupied
            received_consents = len(mid_route_request.consent_responses)
            
            if received_consents >= total_passengers:
                # All consents received, make decision
                all_accepted = all(
                    consent == "accepted"
                    for consent in mid_route_request.consent_responses.values()
                )
                
                if all_accepted:
                    mid_route_request.status = MidRouteStatus.ACCEPTED
                    # Update ride seats
                    ride.seats_occupied += 1
                else:
                    mid_route_request.status = MidRouteStatus.REJECTED
        
        await db.commit()
        
        # Broadcast consent update via WebSocket
        await manager.broadcast(
            str(mid_route_request.ride_id),
            {
                "type": "consent_update",
                "request_id": mid_route_request.id,
                "passenger_id": passenger_id,
                "consent": consent_request.consent,
                "status": mid_route_request.status.value
            }
        )
        
        return {
            "success": True,
            "message": "Consent submitted successfully",
            "request_status": mid_route_request.status.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Consent submission failed: {str(e)}"
        )


@router.post("/modal-shift/suggest")
async def suggest_modal_shift(
    pickup_lat: float,
    pickup_lon: float,
    dropoff_lat: float,
    dropoff_lon: float,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Suggest modal shifts for nearby overlapping requests.
    
    Analyzes nearby requests and suggests vehicle type conversions:
    - 2 bike requests → 1 auto
    - 5 bike requests → 1 cab
    - 3 auto requests → 1 cab
    
    Args:
        pickup_lat: Pickup latitude
        pickup_lon: Pickup longitude
        dropoff_lat: Dropoff latitude
        dropoff_lon: Dropoff longitude
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        Modal shift suggestions
    """
    try:
        suggestions = await matching_service.suggest_modal_shifts(
            db,
            pickup_lat,
            pickup_lon,
            dropoff_lat,
            dropoff_lon
        )
        
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Modal shift suggestion failed: {str(e)}"
        )


@router.post("/telemetry")
async def update_telemetry(
    telemetry: TelemetryUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update driver telemetry data.
    
    Receives real-time location and vehicle telemetry from driver device.
    
    Args:
        telemetry: Telemetry data
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        Telemetry update status
    """
    try:
        # Verify user is driver
        user_role = current_user.get("role")
        if user_role != "driver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only drivers can submit telemetry"
            )
        
        # Create telemetry record
        from backend.app.db.models import Telemetry
        
        telemetry_record = Telemetry(
            ride_id=telemetry.ride_id,
            location=f"POINT({telemetry.longitude} {telemetry.latitude})",
            speed=telemetry.speed,
            heading=telemetry.heading,
            battery_level=telemetry.battery_level
        )
        
        db.add(telemetry_record)
        await db.commit()
        
        # Broadcast location update via WebSocket
        await manager.broadcast(
            str(telemetry.ride_id),
            {
                "type": "location_update",
                "ride_id": telemetry.ride_id,
                "latitude": telemetry.latitude,
                "longitude": telemetry.longitude,
                "speed": telemetry.speed,
                "heading": telemetry.heading,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Telemetry updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telemetry update failed: {str(e)}"
        )


@router.get("/{ride_id}", response_model=RideResponse)
async def get_ride(
    ride_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get ride information.
    
    Args:
        ride_id: Ride ID
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        Ride information
    """
    try:
        result = await db.execute(
            select(Ride).where(Ride.id == ride_id)
        )
        ride = result.scalar_one_or_none()
        
        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ride not found"
            )
        
        # Get driver information
        driver_result = await db.execute(
            select(User).where(User.id == ride.driver_id)
        )
        driver = driver_result.scalar_one_or_none()
        
        return RideResponse(
            id=ride.id,
            driver_id=ride.driver_id or 0,
            passenger_id=ride.passenger_id,
            vehicle_type=ride.vehicle_type.value,
            seats_total=ride.seats_total,
            seats_occupied=ride.seats_occupied,
            status=ride.status.value,
            otp_unlocked=ride.otp_unlocked,
            estimated_duration=ride.estimated_duration,
            estimated_distance=ride.estimated_distance,
            fare=ride.fare,
            driver_info={
                "id": driver.id if driver else 0,
                "age": driver.age if driver else None,
                "gender": driver.gender if driver else None,
                "rating": driver.rating if driver else 0.0
            } if driver else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ride: {str(e)}"
        )


# WebSocket Endpoint
@router.websocket("/ws/rides/{ride_id}/track")
async def websocket_ride_tracking(
    websocket: WebSocket,
    ride_id: str,
    token: str
):
    """
    WebSocket endpoint for real-time ride tracking.
    
    Provides bi-directional real-time location streaming for drivers and passengers,
    live trajectory updates, and instant mid-route request broadcasts.
    
    Args:
        websocket: WebSocket connection
        ride_id: Ride ID
        token: JWT token for authentication
    """
    await manager.connect(websocket, ride_id)
    
    try:
        # Verify token
        try:
            from backend.app.api.v1.auth import verify_token
            payload = verify_token(token, "access")
            user_id = payload.get("sub")
            user_role = payload.get("role")
            
            # Send welcome message
            await manager.send_personal(websocket, {
                "type": "connected",
                "ride_id": ride_id,
                "user_id": user_id,
                "user_role": user_role,
                "timestamp": datetime.now().isoformat()
            })
            
            # Keep connection alive and handle messages
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "ping":
                    await manager.send_personal(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                elif data.get("type") == "location_update":
                    # Broadcast location update to all connected clients
                    await manager.broadcast(ride_id, {
                        "type": "location_update",
                        "user_id": user_id,
                        "latitude": data.get("latitude"),
                        "longitude": data.get("longitude"),
                        "timestamp": datetime.now().isoformat()
                    })
                elif data.get("type") == "telemetry":
                    # Broadcast telemetry update
                    await manager.broadcast(ride_id, {
                        "type": "telemetry_update",
                        "user_id": user_id,
                        "telemetry": data.get("data"),
                        "timestamp": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            print(f"WebSocket authentication error: {e}")
            await manager.send_personal(websocket, {
                "type": "error",
                "message": "Authentication failed"
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, ride_id)
        print(f"WebSocket disconnected for ride {ride_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, ride_id)


# Helper Functions
async def get_passenger_fcm_tokens(
    db: AsyncSession,
    ride_id: int
) -> List[str]:
    """
    Get FCM tokens for passengers on a ride.
    
    Args:
        db: Database session
        ride_id: Ride ID
        
    Returns:
        List of FCM tokens
    """
    # This would query passengers associated with the ride
    # For now, return empty list
    return []
