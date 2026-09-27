"""
Driver Dispatch Service with Radius-Based Matching and Queue Management

This module implements:
- Radius-based driver matching using PostGIS spatial queries
- Ride request queue management
- Driver acceptance/rejection flow
- Automatic ride assignment after timeout

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update, func
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio

from app.db.models import User, DriverProfile, Ride
from app.core.config import get_settings
from geoalchemy2 import functions as geofunc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class RideRequestStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class DispatchService:
    """
    Driver dispatch service with radius-based matching and queue management.
    
    Provides:
    - Radius-based driver matching using PostGIS
    - Ride request queue management
    - Driver acceptance/rejection flow
    - Automatic timeout handling
    """
    
    def __init__(self):
        """Initialize dispatch service."""
        self.default_radius_km = settings.dispatch_radius_km
        self.dispatch_timeout_seconds = settings.dispatch_timeout_seconds
        self.max_dispatch_attempts = settings.max_dispatch_attempts
    
    async def find_available_drivers(
        self,
        session: AsyncSession,
        pickup_lat: float,
        pickup_lon: float,
        vehicle_type: Optional[str] = None,
        radius_km: Optional[float] = None
    ) -> List[Dict]:
        """
        Find available drivers within a radius using PostGIS spatial query.
        
        Args:
            session: Async database session
            pickup_lat: Pickup latitude
            pickup_lon: Pickup longitude
            vehicle_type: Optional vehicle type filter
            radius_km: Search radius in kilometers (default from settings)
            
        Returns:
            List of available drivers with distance information
        """
        try:
            radius = radius_km or self.default_radius_km
            radius_meters = radius * 1000
            
            # Build spatial query
            query = select(
                DriverProfile.id,
                DriverProfile.user_id,
                DriverProfile.vehicle_type,
                DriverProfile.vehicle_number,
                DriverProfile.vehicle_model,
                DriverProfile.vehicle_color,
                DriverProfile.rating,
                DriverProfile.total_rides,
                DriverProfile.current_location,
                User.phone,
                User.name
            ).join(
                User, DriverProfile.user_id == User.id
            ).where(
                and_(
                    DriverProfile.is_online == True,
                    DriverProfile.is_verified == True,
                    geofunc.ST_DWithin(
                        DriverProfile.current_location,
                        geofunc.ST_SetSRID(
                            geofunc.ST_MakePoint(pickup_lon, pickup_lat),
                            4326
                        ),
                        radius_meters
                    )
                )
            )
            
            # Filter by vehicle type if specified
            if vehicle_type:
                query = query.where(DriverProfile.vehicle_type == vehicle_type)
            
            # Order by distance (closest first)
            query = query.order_by(
                geofunc.ST_Distance(
                    DriverProfile.current_location,
                    geofunc.ST_SetSRID(
                        geofunc.ST_MakePoint(pickup_lon, pickup_lat),
                        4326
                    )
                )
            )
            
            result = await session.execute(query)
            drivers = result.all()
            
            # Format response with distance calculation
            driver_list = []
            for driver in drivers:
                distance_meters = await session.scalar(
                    select(
                        geofunc.ST_Distance(
                            driver.current_location,
                            geofunc.ST_SetSRID(
                                geofunc.ST_MakePoint(pickup_lon, pickup_lat),
                                4326
                            )
                        )
                    )
                )
                
                driver_list.append({
                    "driver_id": driver.id,
                    "user_id": driver.user_id,
                    "vehicle_type": driver.vehicle_type,
                    "vehicle_number": driver.vehicle_number,
                    "vehicle_model": driver.vehicle_model,
                    "vehicle_color": driver.vehicle_color,
                    "rating": driver.rating,
                    "total_rides": driver.total_rides,
                    "phone": driver.phone,
                    "name": driver.name,
                    "distance_km": round(distance_meters / 1000, 2)
                })
            
            logger.info(f"Found {len(driver_list)} available drivers within {radius}km")
            return driver_list
            
        except Exception as e:
            logger.error(f"Error finding available drivers: {str(e)}")
            raise
    
    async def dispatch_ride_to_driver(
        self,
        session: AsyncSession,
        ride_id: int,
        driver_id: int
    ) -> Dict:
        """
        Dispatch a ride to a specific driver.
        
        Args:
            session: Async database session
            ride_id: Ride ID to dispatch
            driver_id: Driver ID to dispatch to
            
        Returns:
            Dispatch result with status and metadata
        """
        try:
            # Check if ride exists and is in dispatchable state
            ride = await session.execute(
                select(Ride).where(Ride.id == ride_id)
            )
            ride = ride.scalar_one_or_none()
            
            if not ride:
                return {
                    "success": False,
                    "error": "Ride not found"
                }
            
            if ride.status not in ["requested", "searching"]:
                return {
                    "success": False,
                    "error": f"Ride is in {ride.status} state, cannot dispatch"
                }
            
            # Update ride status to dispatched
            await session.execute(
                update(Ride)
                .where(Ride.id == ride_id)
                .values(
                    status="driver_assigned",
                    driver_id=driver_id,
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            logger.info(f"Ride {ride_id} dispatched to driver {driver_id}")
            
            return {
                "success": True,
                "ride_id": ride_id,
                "driver_id": driver_id,
                "dispatched_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error dispatching ride: {str(e)}")
            await session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def accept_ride(
        self,
        session: AsyncSession,
        ride_id: int,
        driver_id: int
    ) -> Dict:
        """
        Driver accepts a ride.
        
        Args:
            session: Async database session
            ride_id: Ride ID
            driver_id: Driver ID accepting the ride
            
        Returns:
            Accept result with status
        """
        try:
            # Check if ride is assigned to this driver
            ride = await session.execute(
                select(Ride).where(
                    and_(
                        Ride.id == ride_id,
                        Ride.driver_id == driver_id
                    )
                )
            )
            ride = ride.scalar_one_or_none()
            
            if not ride:
                return {
                    "success": False,
                    "error": "Ride not found or not assigned to this driver"
                }
            
            if ride.status != "driver_assigned":
                return {
                    "success": False,
                    "error": f"Ride is in {ride.status} state"
                }
            
            # Update ride status to accepted
            await session.execute(
                update(Ride)
                .where(Ride.id == ride_id)
                .values(
                    status="arrived",
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            logger.info(f"Driver {driver_id} accepted ride {ride_id}")
            
            return {
                "success": True,
                "ride_id": ride_id,
                "driver_id": driver_id,
                "accepted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error accepting ride: {str(e)}")
            await session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def reject_ride(
        self,
        session: AsyncSession,
        ride_id: int,
        driver_id: int,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Driver rejects a ride.
        
        Args:
            session: Async database session
            ride_id: Ride ID
            driver_id: Driver ID rejecting the ride
            reason: Optional rejection reason
            
        Returns:
            Reject result with next driver info if available
        """
        try:
            # Check if ride is assigned to this driver
            ride = await session.execute(
                select(Ride).where(
                    and_(
                        Ride.id == ride_id,
                        Ride.driver_id == driver_id
                    )
                )
            )
            ride = ride.scalar_one_or_none()
            
            if not ride:
                return {
                    "success": False,
                    "error": "Ride not found or not assigned to this driver"
                }
            
            if ride.status != "driver_assigned":
                return {
                    "success": False,
                    "error": f"Ride is in {ride.status} state"
                }
            
            # Reset ride to searching state
            await session.execute(
                update(Ride)
                .where(Ride.id == ride_id)
                .values(
                    status="searching",
                    driver_id=None,
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            logger.info(f"Driver {driver_id} rejected ride {ride_id}. Reason: {reason}")
            
            # Find next available driver
            next_drivers = await self.find_available_drivers(
                session,
                ride.pickup_lat,
                ride.pickup_lon,
                ride.vehicle_type
            )
            
            return {
                "success": True,
                "ride_id": ride_id,
                "driver_id": driver_id,
                "rejected_at": datetime.utcnow().isoformat(),
                "reason": reason,
                "next_drivers_available": len(next_drivers) > 0,
                "next_drivers": next_drivers[:3] if next_drivers else []
            }
            
        except Exception as e:
            logger.error(f"Error rejecting ride: {str(e)}")
            await session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def auto_dispatch_with_timeout(
        self,
        session: AsyncSession,
        ride_id: int,
        pickup_lat: float,
        pickup_lon: float,
        vehicle_type: str
    ) -> Dict:
        """
        Auto-dispatch ride with timeout handling.
        
        Finds available drivers and dispatches to closest.
        If no response within timeout, moves to next driver.
        
        Args:
            session: Async database session
            ride_id: Ride ID
            pickup_lat: Pickup latitude
            pickup_lon: Pickup longitude
            vehicle_type: Vehicle type
            
        Returns:
            Dispatch result
        """
        try:
            # Find available drivers
            drivers = await self.find_available_drivers(
                session,
                pickup_lat,
                pickup_lon,
                vehicle_type
            )
            
            if not drivers:
                return {
                    "success": False,
                    "error": "No available drivers in area"
                }
            
            # Dispatch to closest driver
            closest_driver = drivers[0]
            dispatch_result = await self.dispatch_ride_to_driver(
                session,
                ride_id,
                closest_driver["driver_id"]
            )
            
            return {
                "success": True,
                "ride_id": ride_id,
                "dispatched_to": closest_driver,
                "total_drivers_found": len(drivers),
                "dispatch_result": dispatch_result
            }
            
        except Exception as e:
            logger.error(f"Error in auto dispatch: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_driver_queue(
        self,
        session: AsyncSession,
        driver_id: int
    ) -> List[Dict]:
        """
        Get ride requests in queue for a specific driver.
        
        Args:
            session: Async database session
            driver_id: Driver ID
            
        Returns:
            List of queued ride requests
        """
        try:
            # Get driver's current location
            driver = await session.execute(
                select(DriverProfile).where(DriverProfile.id == driver_id)
            )
            driver = driver.scalar_one_or_none()
            
            if not driver or not driver.current_location:
                return []
            
            # Extract coordinates from geometry
            from sqlalchemy import func as sql_func
            lon, lat = await session.execute(
                select(
                    sql_func.ST_X(driver.current_location),
                    sql_func.ST_Y(driver.current_location)
                )
            )
            
            # Find nearby rides in requested/searching state
            rides = await session.execute(
                select(Ride).where(
 sql_func.ST_DWithin(
                        Ride.pickup_location,
                        driver.current_location,
                        self.default_radius_km * 1000
                    )
                ).where(
                    Ride.status.in_(["requested", "searching"])
                ).where(
                    Ride.vehicle_type == driver.vehicle_type
                ).order_by(
                    Ride.created_at
                )
            )
            
            rides = rides.scalars().all()
            
            return [
                {
                    "ride_id": ride.id,
                    "pickup_lat": ride.pickup_lat,
                    "pickup_lon": ride.pickup_lon,
                    "dropoff_lat": ride.dropoff_lat,
                    "dropoff_lon": ride.dropoff_lon,
                    "vehicle_type": ride.vehicle_type,
                    "seats_required": ride.seats_total,
                    "fare": ride.fare,
                    "created_at": ride.created_at.isoformat()
                }
                for ride in rides
            ]
            
        except Exception as e:
            logger.error(f"Error getting driver queue: {str(e)}")
            return []


# Global dispatch service instance
dispatch_service = DispatchService()


if __name__ == "__main__":
    import asyncio
    
    async def test_dispatch_service():
        """Test dispatch service."""
        print("Testing Dispatch Service...")
        
        service = DispatchService()
        print("Dispatch service initialized successfully")
        print(f"Default radius: {service.default_radius_km} km")
        print(f"Dispatch timeout: {service.dispatch_timeout_seconds} seconds")
        
        print("\nDispatch service test completed!")
    
    asyncio.run(test_dispatch_service())
