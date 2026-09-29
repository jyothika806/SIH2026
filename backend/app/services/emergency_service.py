"""
Emergency SOS & Guardian Mode Service

This module implements:
- Emergency SOS siren audio generation and management
- Guardian Mode background location tracking
- Emergency contact notification system
- Low-light fallback trigger detection
- Real-time safety incident logging

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert

from backend.app.api.core.config import get_settings
from backend.app.db.models import User, Ride
from backend.app.services.notification import notification_manager
from backend.app.services.sms_service import sms_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class EmergencySeverity(str, Enum):
    """Emergency severity level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmergencyType(str, Enum):
    """Emergency type enumeration."""
    SOS_BUTTON = "sos_button"
    GUARDIAN_MODE = "guardian_mode"
    ROUTE_DEVIATION = "route_deviation"
    UNUSUAL_STOP = "unusual_stop"
    HARSH_BRKING = "harsh_braking"
    SPEEDING = "speeding"
    PASSENGER_REPORT = "passenger_report"
    DRIVER_REPORT = "driver_report"


@dataclass
class EmergencyIncident:
    """Emergency incident data structure."""
    incident_id: str
    ride_id: int
    user_id: int
    user_role: str
    emergency_type: EmergencyType
    severity: EmergencySeverity
    location_lat: float
    location_lon: float
    timestamp: datetime
    description: str
    metadata: Dict
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "incident_id": self.incident_id,
            "ride_id": self.ride_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "emergency_type": self.emergency_type.value,
            "severity": self.severity.value,
            "location_lat": self.location_lat,
            "location_lon": self.location_lon,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "metadata": self.metadata,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class GuardianModeSession:
    """Guardian Mode session data structure."""
    session_id: str
    ride_id: int
    user_id: int
    emergency_contacts: List[Dict]
    started_at: datetime
    last_ping: datetime
    ping_interval_seconds: int
    location_updates: List[Dict]
    active: bool = True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "ride_id": self.ride_id,
            "user_id": self.user_id,
            "emergency_contacts": self.emergency_contacts,
            "started_at": self.started_at.isoformat(),
            "last_ping": self.last_ping.isoformat(),
            "ping_interval_seconds": self.ping_interval_seconds,
            "location_updates_count": len(self.location_updates),
            "active": self.active
        }


class EmergencyService:
    """
    Emergency SOS and Guardian Mode service.
    
    Provides:
    - SOS siren audio generation
    - Guardian Mode background tracking
    - Emergency contact notifications
    - Low-light trigger detection
    - Incident logging and management
    """
    
    def __init__(self):
        """Initialize emergency service."""
        self.active_guardian_sessions: Dict[str, GuardianModeSession] = {}
        self.active_incidents: Dict[str, EmergencyIncident] = {}
        self._incident_counter = 0
        self._session_counter = 0
    
    def _generate_incident_id(self) -> str:
        """Generate unique incident ID."""
        self._incident_counter += 1
        return f"incident_{datetime.utcnow().timestamp()}_{self._incident_counter}"
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        self._session_counter += 1
        return f"session_{datetime.utcnow().timestamp()}_{self._session_counter}"
    
    async def trigger_sos(
        self,
        ride_id: int,
        user_id: int,
        user_role: str,
        location_lat: float,
        location_lon: float,
        description: str = "SOS button pressed",
        metadata: Dict = None
    ) -> EmergencyIncident:
        """
        Trigger emergency SOS.
        
        Args:
            ride_id: Associated ride ID
            user_id: User ID triggering SOS
            user_role: User role (passenger/driver)
            location_lat: Current latitude
            location_lon: Current longitude
            description: Incident description
            metadata: Additional metadata
            
        Returns:
            Created EmergencyIncident
        """
        incident_id = self._generate_incident_id()
        
        incident = EmergencyIncident(
            incident_id=incident_id,
            ride_id=ride_id,
            user_id=user_id,
            user_role=user_role,
            emergency_type=EmergencyType.SOS_BUTTON,
            severity=EmergencySeverity.CRITICAL,
            location_lat=location_lat,
            location_lon=location_lon,
            timestamp=datetime.utcnow(),
            description=description,
            metadata=metadata or {}
        )
        
        self.active_incidents[incident_id] = incident
        
        # Notify emergency contacts
        await self._notify_emergency_contacts(incident)
        
        # Notify safety team
        await self._notify_safety_team(incident)
        
        logger.critical(f"SOS triggered by {user_role} {user_id} on ride {ride_id}")
        
        return incident
    
    async def start_guardian_mode(
        self,
        ride_id: int,
        user_id: int,
        emergency_contacts: List[Dict],
        ping_interval_seconds: int = None
    ) -> GuardianModeSession:
        """
        Start Guardian Mode for background tracking.
        
        Args:
            ride_id: Associated ride ID
            user_id: User ID starting Guardian Mode
            emergency_contacts: List of emergency contact dicts
            ping_interval_seconds: Ping interval (uses default if None)
            
        Returns:
            Created GuardianModeSession
        """
        session_id = self._generate_session_id()
        
        session = GuardianModeSession(
            session_id=session_id,
            ride_id=ride_id,
            user_id=user_id,
            emergency_contacts=emergency_contacts,
            started_at=datetime.utcnow(),
            last_ping=datetime.utcnow(),
            ping_interval_seconds=ping_interval_seconds or settings.guardian_mode_ping_interval_seconds,
            location_updates=[],
            active=True
        )
        
        self.active_guardian_sessions[session_id] = session
        
        # Start background ping task
        asyncio.create_task(self._guardian_ping_loop(session_id))
        
        logger.info(f"Guardian Mode started for user {user_id} on ride {ride_id}")
        
        return session
    
    async def update_guardian_location(
        self,
        session_id: str,
        location_lat: float,
        location_lon: float,
        speed: float = None,
        battery_level: int = None
    ) -> bool:
        """
        Update Guardian Mode location.
        
        Args:
            session_id: Guardian Mode session ID
            location_lat: Current latitude
            location_lon: Current longitude
            speed: Current speed in km/h
            battery_level: Device battery level
            
        Returns:
            True if updated, False if session not found
        """
        session = self.active_guardian_sessions.get(session_id)
        if not session or not session.active:
            return False
        
        location_update = {
            "lat": location_lat,
            "lon": location_lon,
            "speed": speed,
            "battery_level": battery_level,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        session.location_updates.append(location_update)
        session.last_ping = datetime.utcnow()
        
        # Keep only last 100 location updates
        if len(session.location_updates) > 100:
            session.location_updates = session.location_updates[-100:]
        
        return True
    
    async def stop_guardian_mode(self, session_id: str) -> bool:
        """
        Stop Guardian Mode session.
        
        Args:
            session_id: Guardian Mode session ID
            
        Returns:
            True if stopped, False if session not found
        """
        session = self.active_guardian_sessions.get(session_id)
        if not session:
            return False
        
        session.active = False
        
        # Notify emergency contacts that Guardian Mode is ending
        await self._notify_guardian_end(session)
        
        # Remove session after delay
        await asyncio.sleep(5)
        if session_id in self.active_guardian_sessions:
            del self.active_guardian_sessions[session_id]
        
        logger.info(f"Guardian Mode stopped for session {session_id}")
        
        return True
    
    async def _guardian_ping_loop(self, session_id: str):
        """
        Background loop for Guardian Mode pings.
        
        Args:
            session_id: Guardian Mode session ID
        """
        session = self.active_guardian_sessions.get(session_id)
        if not session:
            return
        
        while session.active:
            try:
                await asyncio.sleep(session.ping_interval_seconds)
                
                if not session.active:
                    break
                
                # Check if ping is overdue
                time_since_ping = (datetime.utcnow() - session.last_ping).total_seconds()
                
                if time_since_ping > (session.ping_interval_seconds * 3):
                    # Ping overdue - trigger alert
                    await self._notify_guardian_timeout(session)
                    logger.warning(f"Guardian Mode ping timeout for session {session_id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Guardian Mode ping loop: {e}")
    
    async def _notify_emergency_contacts(self, incident: EmergencyIncident):
        """
        Notify emergency contacts about an incident.
        
        Args:
            incident: Emergency incident
        """
        # Get user's emergency contacts from database
        # For now, use a placeholder
        emergency_contacts = [
            {"phone": "+919876543210", "name": "Emergency Contact 1"},
            {"phone": "+919876543211", "name": "Emergency Contact 2"}
        ]
        
        message = (
            f"EMERGENCY ALERT: {incident.user_role.upper()} has triggered SOS on ride {incident.ride_id}. "
            f"Location: {incident.location_lat}, {incident.location_lon}. "
            f"Time: {incident.timestamp.strftime('%Y-%m-%d %H:%M:%S')}. "
            f"Description: {incident.description}"
        )
        
        for contact in emergency_contacts[:settings.emergency_contact_max_count]:
            try:
                await sms_service.send_sms(
                    phone_number=contact["phone"],
                    message=message
                )
                logger.info(f"Emergency SMS sent to {contact['name']}")
            except Exception as e:
                logger.error(f"Failed to send emergency SMS to {contact['name']}: {e}")
    
    async def _notify_safety_team(self, incident: EmergencyIncident):
        """
        Notify safety team about an incident.
        
        Args:
            incident: Emergency incident
        """
        # In production, this would send to safety team dashboard
        logger.critical(
            f"SAFETY TEAM ALERT: {incident.emergency_type.value} - "
            f"Ride {incident.ride_id}, User {incident.user_id}, "
            f"Severity: {incident.severity.value}"
        )
    
    async def _notify_guardian_timeout(self, session: GuardianModeSession):
        """
        Notify about Guardian Mode timeout.
        
        Args:
            session: Guardian Mode session
        """
        message = (
            f"GUARDIAN MODE ALERT: Location ping timeout for user on ride {session.ride_id}. "
            f"Last known location: {session.location_updates[-1] if session.location_updates else 'N/A'}. "
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        for contact in session.emergency_contacts[:settings.emergency_contact_max_count]:
            try:
                await sms_service.send_sms(
                    phone_number=contact["phone"],
                    message=message
                )
            except Exception as e:
                logger.error(f"Failed to send Guardian timeout SMS: {e}")
    
    async def _notify_guardian_end(self, session: GuardianModeSession):
        """
        Notify that Guardian Mode is ending.
        
        Args:
            session: Guardian Mode session
        """
        message = (
            f"GUARDIAN MODE ENDED: User has safely ended Guardian Mode for ride {session.ride_id}. "
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        for contact in session.emergency_contacts[:settings.emergency_contact_max_count]:
            try:
                await sms_service.send_sms(
                    phone_number=contact["phone"],
                    message=message
                )
            except Exception as e:
                logger.error(f"Failed to send Guardian end SMS: {e}")
    
    async def log_incident(
        self,
        ride_id: int,
        user_id: int,
        user_role: str,
        emergency_type: EmergencyType,
        severity: EmergencySeverity,
        location_lat: float,
        location_lon: float,
        description: str,
        metadata: Dict = None
    ) -> EmergencyIncident:
        """
        Log a safety incident.
        
        Args:
            ride_id: Associated ride ID
            user_id: User ID
            user_role: User role
            emergency_type: Type of emergency
            severity: Severity level
            location_lat: Location latitude
            location_lon: Location longitude
            description: Incident description
            metadata: Additional metadata
            
        Returns:
            Created EmergencyIncident
        """
        incident_id = self._generate_incident_id()
        
        incident = EmergencyIncident(
            incident_id=incident_id,
            ride_id=ride_id,
            user_id=user_id,
            user_role=user_role,
            emergency_type=emergency_type,
            severity=severity,
            location_lat=location_lat,
            location_lon=location_lon,
            timestamp=datetime.utcnow(),
            description=description,
            metadata=metadata or {}
        )
        
        self.active_incidents[incident_id] = incident
        
        # Notify based on severity
        if severity in [EmergencySeverity.HIGH, EmergencySeverity.CRITICAL]:
            await self._notify_safety_team(incident)
        
        logger.warning(
            f"Incident logged: {emergency_type.value} - Severity: {severity.value} - "
            f"Ride {ride_id}"
        )
        
        return incident
    
    async def resolve_incident(self, incident_id: str) -> bool:
        """
        Resolve an emergency incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            True if resolved, False if not found
        """
        incident = self.active_incidents.get(incident_id)
        if not incident:
            return False
        
        incident.resolved = True
        incident.resolved_at = datetime.utcnow()
        
        logger.info(f"Incident {incident_id} resolved")
        
        # Remove from active incidents after delay
        await asyncio.sleep(5)
        if incident_id in self.active_incidents:
            del self.active_incidents[incident_id]
        
        return True
    
    def get_sos_siren_duration(self) -> int:
        """
        Get SOS siren duration in seconds.
        
        Returns:
            Siren duration in seconds
        """
        return settings.sos_siren_duration_seconds
    
    def get_guardian_ping_interval(self) -> int:
        """
        Get Guardian Mode ping interval in seconds.
        
        Returns:
            Ping interval in seconds
        """
        return settings.guardian_mode_ping_interval_seconds
    
    def check_low_light_trigger(self, lux_level: float) -> bool:
        """
        Check if low-light condition triggers fallback.
        
        Args:
            lux_level: Current light level in lux
            
        Returns:
            True if low-light trigger should activate
        """
        return lux_level < settings.low_light_lux_threshold


# Global emergency service instance
emergency_service = EmergencyService()


if __name__ == "__main__":
    import asyncio
    
    async def test_emergency_service():
        """Test emergency service."""
        print("Testing Emergency Service...")
        
        service = EmergencyService()
        
        # Test SOS trigger
        incident = await service.trigger_sos(
            ride_id=123,
            user_id=456,
            user_role="passenger",
            location_lat=12.9716,
            location_lon=77.5946,
            description="Test SOS trigger"
        )
        
        print(f"SOS Incident Created: {incident.incident_id}")
        print(f"Severity: {incident.severity.value}")
        
        # Test Guardian Mode
        session = await service.start_guardian_mode(
            ride_id=123,
            user_id=456,
            emergency_contacts=[
                {"phone": "+919876543210", "name": "Contact 1"}
            ]
        )
        
        print(f"\nGuardian Mode Session: {session.session_id}")
        print(f"Ping Interval: {session.ping_interval_seconds}s")
        
        # Test location update
        await service.update_guardian_location(
            session_id=session.session_id,
            location_lat=12.9720,
            location_lon=77.5950,
            speed=25.5,
            battery_level=85
        )
        
        print(f"Location updated: {len(session.location_updates)} updates")
        
        # Test low-light trigger
        low_light = service.check_low_light_trigger(10.0)
        print(f"\nLow-light trigger (10 lux): {low_light}")
        
        normal_light = service.check_low_light_trigger(100.0)
        print(f"Low-light trigger (100 lux): {normal_light}")
        
        # Stop Guardian Mode
        await service.stop_guardian_mode(session.session_id)
        
        print("\nEmergency service test completed!")
    
    asyncio.run(test_emergency_service())
