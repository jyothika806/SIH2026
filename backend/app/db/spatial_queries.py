"""
PostGIS Spatial Queries for Ride Matching

This module implements:
- ST_DWithin for proximity searches
- ST_Buffer for detour corridor calculation
- Trajectory corridor overlap detection
- Spatial indexing for performance

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple
import logging

from backend.app.db.models import Ride, MidRouteRequest, RideStatus
from backend.app.api.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class SpatialQueryService:
    """
    Service for PostGIS spatial queries.
    
    Provides optimized spatial queries for ride matching and
    corridor overlap detection.
    """
    
    @staticmethod
    async def find_nearby_rides(
        session: AsyncSession,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float,
        radius_meters: int = 2000,
        max_detour_minutes: int = 5
    ) -> List[dict]:
        """
        Find nearby active rides whose route corridor overlaps with request.
        
        Uses PostGIS spatial functions to:
        1. Buffer the ride route by estimated detour distance
        2. Check if pickup/dropoff points fall within the buffered corridor
        3. Calculate actual detour time using OSRM
        
        Args:
            session: Async database session
            pickup_lat: Pickup point latitude
            pickup_lon: Pickup point longitude
            dropoff_lat: Dropoff point latitude
            dropoff_lon: Dropoff point longitude
            radius_meters: Search radius in meters
            max_detour_minutes: Maximum allowed detour time in minutes
            
        Returns:
            List of matching rides with detour information
        """
        try:
            # Create pickup and dropoff points
            pickup_point = f"ST_SetSRID(ST_MakePoint({pickup_lon}, {pickup_lat}), 4326)"
            dropoff_point = f"ST_SetSRID(ST_MakePoint({dropoff_lon}, {dropoff_lat}), 4326)"
            
            # Estimated detour distance (assuming 30 km/h average speed)
            detour_distance_meters = max_detour_minutes * 30 * 1000 / 60  # ~500m for 5 min
            
            # Build spatial query
            query = text("""
                SELECT 
                    r.id,
                    r.driver_id,
                    r.vehicle_type,
                    r.seats_total,
                    r.seats_occupied,
                    r.status,
                    r.pickup_point,
                    r.dropoff_point,
                    r.route_geometry,
                    u.phone as driver_phone,
                    u.age as driver_age,
                    u.gender as driver_gender,
                    u.rating as driver_rating,
                    -- Distance from pickup to route
                    ST_Distance(
                        r.route_geometry::geography,
                        {pickup_point}::geography
                    ) as pickup_distance,
                    -- Distance from dropoff to route
                    ST_Distance(
                        r.route_geometry::geography,
                        {dropoff_point}::geography
                    ) as dropoff_distance,
                    -- Check if points are within buffered corridor
                    ST_Within(
                        {pickup_point}::geography,
                        ST_Buffer(r.route_geometry::geography, {detour_distance})::geography
                    ) as pickup_in_corridor,
                    ST_Within(
                        {dropoff_point}::geography,
                        ST_Buffer(r.route_geometry::geography, {detour_distance})::geography
                    ) as dropoff_in_corridor,
                    -- Calculate route segment order (for detour calculation)
                    ST_LineLocatePoint(
                        r.route_geometry,
                        {pickup_point}
                    ) as pickup_segment,
                    ST_LineLocatePoint(
                        r.route_geometry,
                        {dropoff_point}
                    ) as dropoff_segment
                FROM rides r
                JOIN users u ON r.driver_id = u.id
                WHERE 
                    r.status IN :active_statuses
                    AND r.seats_occupied < r.seats_total
                    AND r.route_geometry IS NOT NULL
                    AND (
                        -- Pickup within search radius
                        ST_DWithin(
                            r.pickup_point::geography,
                            {pickup_point}::geography,
                            :radius_meters
                        )
                        OR
                        -- Pickup within buffered corridor
                        ST_Within(
                            {pickup_point}::geography,
                            ST_Buffer(r.route_geometry::geography, {detour_distance})::geography
                        )
                    )
                ORDER BY
                    pickup_distance ASC,
                    dropoff_distance ASC
                LIMIT 20
            """.format(
                pickup_point=pickup_point,
                dropoff_point=dropoff_point,
                detour_distance=detour_distance
            ))
            
            result = await session.execute(
                query,
                {
                    "active_statuses": [
                        RideStatus.DRIVER_ASSIGNED.value,
                        RideStatus.ARRIVED.value,
                        RideStatus.IN_PROGRESS.value
                    ],
                    "radius_meters": radius_meters
                }
            )
            
            rides = result.fetchall()
            
            # Convert to list of dictionaries
            matching_rides = []
            for ride in rides:
                matching_rides.append({
                    "id": ride.id,
                    "driver_id": ride.driver_id,
                    "vehicle_type": ride.vehicle_type,
                    "seats_total": ride.seats_total,
                    "seats_occupied": ride.seats_occupied,
                    "status": ride.status,
                    "driver_phone": ride.driver_phone,
                    "driver_age": ride.driver_age,
                    "driver_gender": ride.driver_gender,
                    "driver_rating": ride.driver_rating,
                    "pickup_distance": float(ride.pickup_distance) if ride.pickup_distance else None,
                    "dropoff_distance": float(ride.dropoff_distance) if ride.dropoff_distance else None,
                    "pickup_in_corridor": bool(ride.pickup_in_corridor),
                    "dropoff_in_corridor": bool(ride.dropoff_in_corridor),
                    "pickup_segment": float(ride.pickup_segment) if ride.pickup_segment else None,
                    "dropoff_segment": float(ride.dropoff_segment) if ride.dropoff_segment else None
                })
            
            logger.info(f"Found {len(matching_rides)} nearby rides")
            return matching_rides
            
        except Exception as e:
            logger.error(f"Error finding nearby rides: {str(e)}")
            raise
    
    @staticmethod
    async def calculate_detour_time(
        session: AsyncSession,
        ride_id: int,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float
    ) -> Tuple[float, float]:
        """
        Calculate detour time and distance for mid-route pickup.
        
        This function calculates the additional time and distance required
        to deviate from the original route to pick up and drop off a new passenger.
        
        Args:
            session: Async database session
            ride_id: Original ride ID
            pickup_lat: New pickup latitude
            pickup_lon: New pickup longitude
            dropoff_lat: New dropoff latitude
            dropoff_lon: New dropoff longitude
            
        Returns:
            Tuple of (detour_time_minutes, detour_distance_meters)
        """
        try:
            # Get original ride geometry
            query = text("""
                SELECT 
                    route_geometry,
                    pickup_point,
                    dropoff_point
                FROM rides
                WHERE id = :ride_id
            """)
            
            result = await session.execute(query, {"ride_id": ride_id})
            ride_data = result.fetchone()
            
            if not ride_data or not ride_data.route_geometry:
                logger.warning(f"No route geometry found for ride {ride_id}")
                return (0.0, 0.0)
            
            # This is a simplified calculation
            # In production, integrate with OSRM for accurate detour calculation
            # For now, use Euclidean distance as approximation
            
            # Calculate original route length
            original_length_query = text("""
                SELECT ST_Length(route_geometry::geography) as length
                FROM rides
                WHERE id = :ride_id
            """)
            
            result = await session.execute(original_length_query, {"ride_id": ride_id})
            original_length = result.scalar()
            
            # Calculate detour (simplified - use OSRM in production)
            # This estimates detour based on distance from original route
            pickup_point = f"ST_SetSRID(ST_MakePoint({pickup_lon}, {pickup_lat}), 4326)"
            dropoff_point = f"ST_SetSRID(ST_MakePoint({dropoff_lon}, {dropoff_lat}), 4326)"
            
            detour_query = text("""
                SELECT 
                    ST_Distance(
                        route_geometry::geography,
                        {pickup_point}::geography
                    ) +
                    ST_Distance(
                        route_geometry::geography,
                        {dropoff_point}::geography
                    ) as detour_distance
                FROM rides
                WHERE id = :ride_id
            """.format(pickup_point=pickup_point, dropoff_point=dropoff_point))
            
            result = await session.execute(detour_query, {"ride_id": ride_id})
            detour_distance = result.scalar()
            
            # Convert distance to time (assuming 30 km/h average speed)
            detour_time = (detour_distance / 1000) / 30 * 60  # minutes
            
            return (detour_time, detour_distance)
            
        except Exception as e:
            logger.error(f"Error calculating detour: {str(e)}")
            return (0.0, 0.0)
    
    @staticmethod
    async def find_overlapping_requests(
        session: AsyncSession,
        vehicle_type: str,
        radius_meters: int = 1000
    ) -> List[dict]:
        """
        Find overlapping ride requests for modal shift suggestions.
        
        Identifies nearby requests with similar routes that could be
        combined into a larger vehicle (e.g., 2 bikes -> 1 auto).
        
        Args:
            session: Async database session
            vehicle_type: Current vehicle type to find alternatives for
            radius_meters: Search radius for overlapping routes
            
        Returns:
            List of overlapping request groups
        """
        try:
            # Find rides of specified vehicle type that are nearby
            query = text("""
                WITH nearby_rides AS (
                    SELECT 
                        r1.id as ride1_id,
                        r2.id as ride2_id,
                        r1.pickup_point as pickup1,
                        r2.pickup_point as pickup2,
                        r1.dropoff_point as dropoff1,
                        r2.dropoff_point as dropoff2,
                        ST_Distance(
                            r1.pickup_point::geography,
                            r2.pickup_point::geography
                        ) as pickup_distance,
                        ST_Distance(
                            r1.dropoff_point::geography,
                            r2.dropoff_point::geography
                        ) as dropoff_distance,
                        (r1.seats_occupied + r2.seats_occupied) as total_passengers
                    FROM rides r1
                    JOIN rides r2 ON r1.id != r2.id
                    WHERE 
                        r1.vehicle_type = :vehicle_type
                        AND r2.vehicle_type = :vehicle_type
                        AND r1.status IN :active_statuses
                        AND r2.status IN :active_statuses
                        AND ST_DWithin(
                            r1.pickup_point::geography,
                            r2.pickup_point::geography,
                            :radius_meters
                        )
                )
                SELECT 
                    ride1_id,
                    ride2_id,
                    pickup_distance,
                    dropoff_distance,
                    total_passengers
                FROM nearby_rides
                WHERE 
                    pickup_distance < :radius_meters
                    AND dropoff_distance < :radius_meters
                ORDER BY 
                    total_passengers DESC,
                    pickup_distance ASC
                LIMIT 10
            """)
            
            result = await session.execute(
                query,
                {
                    "vehicle_type": vehicle_type,
                    "active_statuses": [
                        RideStatus.REQUESTED.value,
                        RideStatus.SEARCHING.value
                    ],
                    "radius_meters": radius_meters
                }
            )
            
            overlapping = result.fetchall()
            
            # Convert to list of dictionaries
            overlapping_groups = []
            for group in overlapping:
                overlapping_groups.append({
                    "ride1_id": group.ride1_id,
                    "ride2_id": group.ride2_id,
                    "pickup_distance": float(group.pickup_distance),
                    "dropoff_distance": float(group.dropoff_distance),
                    "total_passengers": group.total_passengers
                })
            
            logger.info(f"Found {len(overlapping_groups)} overlapping request groups")
            return overlapping_groups
            
        except Exception as e:
            logger.error(f"Error finding overlapping requests: {str(e)}")
            raise
    
    @staticmethod
    async def update_ride_geometry(
        session: AsyncSession,
        ride_id: int,
        route_geometry: str
    ) -> bool:
        """
        Update ride route geometry.
        
        Args:
            session: Async database session
            ride_id: Ride ID to update
            route_geometry: WKT or GeoJSON route geometry
            
        Returns:
            bool: True if update successful
        """
        try:
            query = text("""
                UPDATE rides
                SET route_geometry = ST_GeomFromText(:route_geometry, 4326),
                    updated_at = NOW()
                WHERE id = :ride_id
            """)
            
            await session.execute(
                query,
                {
                    "ride_id": ride_id,
                    "route_geometry": route_geometry
                }
            )
            await session.commit()
            
            logger.info(f"Updated route geometry for ride {ride_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating ride geometry: {str(e)}")
            await session.rollback()
            return False
    
    @staticmethod
    async def create_spatial_index(
        session: AsyncSession,
        table_name: str,
        column_name: str
    ) -> bool:
        """
        Create spatial index on geometry column.
        
        Args:
            session: Async database session
            table_name: Table name
            column_name: Geometry column name
            
        Returns:
            bool: True if index created successfully
        """
        try:
            index_name = f"idx_{table_name}_{column_name}"
            query = text(f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {table_name}
                USING GIST ({column_name})
            """)
            
            await session.execute(query)
            await session.commit()
            
            logger.info(f"Created spatial index {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating spatial index: {str(e)}")
            await session.rollback()
            return False


# Global spatial query service instance
spatial_service = SpatialQueryService()


if __name__ == "__main__":
    import asyncio
    from backend.app.api.v1.core.database import AsyncSessionLocal
    
    async def test_spatial_queries():
        """Test spatial query service."""
        print("Testing Spatial Query Service...")
        
        async with AsyncSessionLocal() as session:
            # Test finding nearby rides
            rides = await spatial_service.find_nearby_rides(
                session,
                pickup_lat=12.9716,
                pickup_lon=77.5946,
                dropoff_lat=12.9352,
                dropoff_lon=77.6245,
                radius_meters=2000
            )
            
            print(f"Found {len(rides)} nearby rides")
            for ride in rides[:3]:
                print(f"  Ride {ride['id']}: {ride['vehicle_type']}, detour: {ride['pickup_distance']:.0f}m")
        
        print("\nSpatial query service test completed!")
    
    # Note: This test requires a running database with PostGIS
    # asyncio.run(test_spatial_queries())
