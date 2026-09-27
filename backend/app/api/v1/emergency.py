"""
Emergency SOS & Guardian Mode API Endpoints

This module implements:
- SOS trigger endpoint
- Guardian Mode start/stop endpoints
- Guardian Mode location update endpoint
- Incident logging endpoint
- Incident resolution endpoint

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from datetime import datetime

from app.api.v1.auth import get_current_user
from app.services.emergency_service import (
    emergency_service, EmergencyIncident, GuardianModeSession,
    EmergencySeverity, EmergencyType
)

router = APIRouter(prefix="/emergency", tags=["Emergency & Safety"])


# Pydantic Schemas
class SOSTriggerRequest(BaseModel):
    """SOS trigger request schema."""
    
    ride_id: int = Field(..., description="Associated ride ID")
    location_lat: float = Field(..., ge=-90, le=90, description="Current latitude")
    location_lon: float = Field(..., ge=-180, le=180, description="Current longitude")
    description: str = Field("SOS button pressed", description="Incident description")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")


class SOSTriggerResponse(BaseModel):
    """SOS trigger response schema."""
    
    incident_id: str = Field(..., description="Incident ID")
    ride_id: int = Field(..., description="Ride ID")
    emergency_type: str = Field(..., description="Emergency type")
    severity: str = Field(..., description="Severity level")
    timestamp: str = Field(..., description="Incident timestamp")
    location: Dict = Field(..., description="Incident location")


class GuardianModeStartRequest(BaseModel):
    """Guardian Mode start request schema."""
    
    ride_id: int = Field(..., description="Associated ride ID")
    emergency_contacts: List[Dict] = Field(..., description="List of emergency contacts")
    ping_interval_seconds: Optional[int] = Field(None, description="Custom ping interval")


class GuardianModeStartResponse(BaseModel):
    """Guardian Mode start response schema."""
    
    session_id: str = Field(..., description="Session ID")
    ride_id: int = Field(..., description="Ride ID")
    started_at: str = Field(..., description="Start timestamp")
    ping_interval_seconds: int = Field(..., description="Ping interval")
    active: bool = Field(..., description="Session active status")


class GuardianLocationUpdateRequest(BaseModel):
    """Guardian Mode location update request schema."""
    
    session_id: str = Field(..., description="Guardian Mode session ID")
    location_lat: float = Field(..., ge=-90, le=90, description="Current latitude")
    location_lon: float = Field(..., ge=-180, le=180, description="Current longitude")
    speed: Optional[float] = Field(None, description="Speed in km/h")
    battery_level: Optional[int] = Field(None, ge=0, le=100, description="Battery level percentage")


class IncidentLogRequest(BaseModel):
    """Incident log request schema."""
    
    ride_id: int = Field(..., description="Associated ride ID")
    emergency_type: Literal[
        "sos_button", "guardian_mode", "route_deviation", "unusual_stop",
        "harsh_braking", "speeding", "passenger_report", "driver_report"
    ] = Field(..., description="Emergency type")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Severity level")
    location_lat: float = Field(..., ge=-90, le=90, description="Location latitude")
    location_lon: float = Field(..., ge=-180, le=180, description="Location longitude")
    description: str = Field(..., description="Incident description")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")


# API Endpoints
@router.post("/sos", response_model=SOSTriggerResponse)
async def trigger_sos(
    request: SOSTriggerRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger emergency SOS.
    
    Activates emergency siren, notifies emergency contacts and safety team,
    and logs the incident.
    
    Args:
        request: SOS trigger data
        current_user: Current user from JWT token
        
    Returns:
        SOSTriggerResponse with incident details
    """
    try:
        user_id = int(current_user.get("sub"))
        user_role = current_user.get("role")
        
        # Trigger SOS
        incident: EmergencyIncident = await emergency_service.trigger_sos(
            ride_id=request.ride_id,
            user_id=user_id,
            user_role=user_role,
            location_lat=request.location_lat,
            location_lon=request.location_lon,
            description=request.description,
            metadata=request.metadata
        )
        
        return SOSTriggerResponse(
            incident_id=incident.incident_id,
            ride_id=incident.ride_id,
            emergency_type=incident.emergency_type.value,
            severity=incident.severity.value,
            timestamp=incident.timestamp.isoformat(),
            location={
                "lat": incident.location_lat,
                "lon": incident.location_lon
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SOS trigger failed: {str(e)}"
        )


@router.post("/guardian/start", response_model=GuardianModeStartResponse)
async def start_guardian_mode(
    request: GuardianModeStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Start Guardian Mode for background tracking.
    
    Enables continuous location tracking with periodic pings to
    emergency contacts.
    
    Args:
        request: Guardian Mode start data
        current_user: Current user from JWT token
        
    Returns:
        GuardianModeStartResponse with session details
    """
    try:
        user_id = int(current_user.get("sub"))
        
        # Start Guardian Mode
        session: GuardianModeSession = await emergency_service.start_guardian_mode(
            ride_id=request.ride_id,
            user_id=user_id,
            emergency_contacts=request.emergency_contacts,
            ping_interval_seconds=request.ping_interval_seconds
        )
        
        return GuardianModeStartResponse(
            session_id=session.session_id,
            ride_id=session.ride_id,
            started_at=session.started_at.isoformat(),
            ping_interval_seconds=session.ping_interval_seconds,
            active=session.active
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start Guardian Mode: {str(e)}"
        )


@router.post("/guardian/update")
async def update_guardian_location(
    request: GuardianLocationUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update Guardian Mode location.
    
    Submits periodic location updates during Guardian Mode.
    
    Args:
        request: Location update data
        current_user: Current user from JWT token
        
    Returns:
        Update status
    """
    try:
        success = await emergency_service.update_guardian_location(
            session_id=request.session_id,
            location_lat=request.location_lat,
            location_lon=request.location_lon,
            speed=request.speed,
            battery_level=request.battery_level
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guardian Mode session not found or inactive"
            )
        
        return {
            "success": True,
            "message": "Location updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update Guardian location: {str(e)}"
        )


@router.post("/guardian/stop/{session_id}")
async def stop_guardian_mode(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Stop Guardian Mode session.
    
    Ends background tracking and notifies emergency contacts.
    
    Args:
        session_id: Guardian Mode session ID
        current_user: Current user from JWT token
        
    Returns:
        Stop status
    """
    try:
        success = await emergency_service.stop_guardian_mode(session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guardian Mode session not found"
            )
        
        return {
            "success": True,
            "message": f"Guardian Mode session {session_id} stopped successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop Guardian Mode: {str(e)}"
        )


@router.post("/log")
async def log_incident(
    request: IncidentLogRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Log a safety incident.
    
    Records various safety events (route deviation, harsh braking, etc.)
    for monitoring and alerting.
    
    Args:
        request: Incident log data
        current_user: Current user from JWT token
        
    Returns:
        Logged incident details
    """
    try:
        user_id = int(current_user.get("sub"))
        user_role = current_user.get("role")
        
        # Convert strings to enums
        emergency_type = EmergencyType(request.emergency_type)
        severity = EmergencySeverity(request.severity)
        
        # Log incident
        incident: EmergencyIncident = await emergency_service.log_incident(
            ride_id=request.ride_id,
            user_id=user_id,
            user_role=user_role,
            emergency_type=emergency_type,
            severity=severity,
            location_lat=request.location_lat,
            location_lon=request.location_lon,
            description=request.description,
            metadata=request.metadata
        )
        
        return {
            "success": True,
            "incident": incident.to_dict()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log incident: {str(e)}"
        )


@router.post("/resolve/{incident_id}")
async def resolve_incident(
    incident_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Resolve an emergency incident.
    
    Marks an incident as resolved and stops active alerts.
    
    Args:
        incident_id: Incident ID
        current_user: Current user from JWT token
        
    Returns:
        Resolution status
    """
    try:
        success = await emergency_service.resolve_incident(incident_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        return {
            "success": True,
            "message": f"Incident {incident_id} resolved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve incident: {str(e)}"
        )


@router.get("/config")
async def get_emergency_config():
    """
    Get emergency service configuration.
    
    Returns configuration values for SOS siren duration,
    Guardian Mode ping interval, and low-light threshold.
    
    Returns:
        Emergency configuration
    """
    return {
        "sos_siren_duration_seconds": emergency_service.get_sos_siren_duration(),
        "guardian_ping_interval_seconds": emergency_service.get_guardian_ping_interval(),
        "low_light_lux_threshold": 15.0,
        "emergency_contact_max_count": 5
    }


@router.post("/check-low-light")
async def check_low_light_trigger(
    lux_level: float
):
    """
    Check if low-light condition triggers fallback.
    
    Args:
        lux_level: Current light level in lux
        
    Returns:
        Whether low-light trigger should activate
    """
    trigger = emergency_service.check_low_light_trigger(lux_level)
    
    return {
        "lux_level": lux_level,
        "trigger_fallback": trigger,
        "threshold": 15.0
    }
