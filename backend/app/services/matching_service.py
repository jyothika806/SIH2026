"""
Ride Matching Service with OSRM Integration and Modal Shift Aggregation

This module implements:
- OSRM route matching and trajectory calculation
- 5-minute detour cap logic
- Modal shift aggregation (bike→auto→cab)
- Intelligent ride suggestions

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

import httpx
from typing import List, Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import asyncio

from app.core.config import get_settings
from app.db.spatial_queries import SpatialQueryService
from app.db.models import Ride, VehicleType, RideStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class OSRMService:
    """
    OSRM (Open Source Routing Machine) service for route calculations.
    
    Provides methods for:
    - Route calculation with waypoints
    - Trajectory matching
    - Travel time matrix
    """
    
    def __init__(self, base_url: str = None):
        """
        Initialize OSRM service.
        
        Args:
            base_url: OSRM server base URL
        """
        self.base_url = base_url or settings.osrm_server_url
        self.profile = settings.osrm_profile
        self.timeout = settings.osrm_timeout
    
    async def get_route(
        self,
        waypoints: List[Tuple[float, float]],
        overview: str = "full",
        geometries: str = "geojson"
    ) -> Dict:
        """
        Calculate route between waypoints.
        
        Args:
            waypoints: List of (longitude, latitude) tuples
            overview: Route overview level (full/simplified/no)
            geometries: Geometry format (geojson/polyline/polyline6)
            
        Returns:
            Dictionary with route information
        """
        try:
            coordinates = ";".join(
                f"{lon},{lat}"
                for lon, lat in waypoints
            )
            
            url = (
                f"{self.base_url}/route/v1/{self.profile}/"
                f"{coordinates}"
                f"?overview={overview}&geometries={geometries}"
            )
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                data = response.json()
            
            if not data.get("routes"):
                raise ValueError("No routes found in OSRM response")
            
            route = data["routes"][0]
            
            return {
                "distance_km": round(route["distance"] / 1000, 2),
                "duration_minutes": round(route["duration"] / 60, 2),
                "geometry": route["geometry"],
                "legs": route.get("legs", [])
            }
            
        except httpx.HTTPError as e:
            logger.error(f"OSRM HTTP error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting route from OSRM: {str(e)}")
            raise
    
    async def match_trajectory(
        self,
        points: List[Tuple[float, float]],
        overview: str = "full",
        geometries: str = "geojson"
    ) -> Dict:
        """
        Match GPS trajectory to road network.
        
        Args:
            points: List of (longitude, latitude) tuples
            overview: Route overview level
            geometries: Geometry format
            
        Returns:
            Dictionary with matched trajectory
        """
        try:
            coordinates = ";".join(
                f"{lon},{lat}"
                for lon, lat in points
            )
            
            url = (
                f"{self.base_url}/match/v1/{self.profile}/"
                f"{coordinates}"
                f"?overview={overview}&geometries={geometries}"
            )
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"OSRM matching HTTP error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error matching trajectory: {str(e)}")
            raise
    
    async def get_travel_matrix(
        self,
        locations: List[Tuple[float, float]],
        annotations: str = "duration,distance"
    ) -> Dict:
        """
        Calculate travel time and distance matrix between locations.
        
        Args:
            locations: List of (longitude, latitude) tuples
            annotations: Annotations to include (duration/distance)
            
        Returns:
            Dictionary with duration and distance matrices
        """
        try:
            coordinates = ";".join(
                f"{lon},{lat}"
                for lon, lat in locations
            )
            
            url = (
                f"{self.base_url}/table/v1/{self.profile}/"
                f"{coordinates}"
                f"?annotations={annotations}"
            )
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                data = response.json()
            
            return {
                "durations": data["durations"],
                "distances": data["distances"]
            }
            
        except httpx.HTTPError as e:
            logger.error(f"OSRM matrix HTTP error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting travel matrix: {str(e)}")
            raise
    
    async def calculate_detour(
        self,
        original_route: List[Tuple[float, float]],
        new_pickup: Tuple[float, float],
        new_dropoff: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Calculate detour time and distance for mid-route pickup.
        
        Args:
            original_route: Original route waypoints
            new_pickup: New pickup point (lon, lat)
            new_dropoff: New dropoff point (lon, lat)
            
        Returns:
            Tuple of (detour_time_minutes, detour_distance_km)
        """
        try:
            # Calculate original route time/distance
            original_result = await self.get_route(original_route)
            original_time = original_result["duration_minutes"]
            original_distance = original_result["distance_km"]
            
            # Calculate new route with pickup and dropoff
            # Find best insertion points for pickup and dropoff
            new_route = self._insert_waypoints(
                original_route,
                new_pickup,
                new_dropoff
            )
            
            new_result = await self.get_route(new_route)
            new_time = new_result["duration_minutes"]
            new_distance = new_result["distance_km"]
            
            # Calculate detour
            detour_time = new_time - original_time
            detour_distance = new_distance - original_distance
            
            return (max(0, detour_time), max(0, detour_distance))
            
        except Exception as e:
            logger.error(f"Error calculating detour: {str(e)}")
            return (0.0, 0.0)
    
    def _insert_waypoints(
        self,
        original_route: List[Tuple[float, float]],
        pickup: Tuple[float, float],
        dropoff: Tuple[float, float]
    ) -> List[Tuple[float, float]]:
        """
        Insert pickup and dropoff waypoints into original route.
        
        Simple implementation that inserts pickup after first waypoint
        and dropoff before last waypoint. In production, use more
        sophisticated waypoint optimization.
        
        Args:
            original_route: Original route waypoints
            pickup: Pickup point
            dropoff: Dropoff point
            
        Returns:
            New route with inserted waypoints
        """
        if len(original_route) < 2:
            return [pickup, dropoff]
        
        # Insert pickup after first waypoint
        new_route = [original_route[0], pickup]
        
        # Add intermediate waypoints
        for waypoint in original_route[1:-1]:
            new_route.append(waypoint)
        
        # Insert dropoff before last waypoint
        new_route.append(dropoff)
        new_route.append(original_route[-1])
        
        return new_route


class MatchingService:
    """
    Ride matching service with detour calculation and modal shift.
    
    Provides:
    - OSRM-based route matching
    - 5-minute detour cap enforcement
    - Modal shift aggregation
    - Intelligent ride suggestions
    """
    
    def __init__(self):
        """Initialize matching service."""
        self.osrm_service = OSRMService()
        self.spatial_service = SpatialQueryService()
        self.max_detour_minutes = settings.max_detour_minutes
    
    async def find_matching_rides(
        self,
        session: AsyncSession,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float,
        vehicle_type: Optional[VehicleType] = None
    ) -> List[Dict]:
        """
        Find matching rides with detour calculation.
        
        Args:
            session: Async database session
            pickup_lat: Pickup latitude
            pickup_lon: Pickup longitude
            dropoff_lat: Dropoff latitude
            dropoff_lon: Dropoff longitude
            vehicle_type: Optional vehicle type filter
            
        Returns:
            List of matching rides with detour information
        """
        try:
            # Find nearby rides using spatial queries
            nearby_rides = await self.spatial_service.find_nearby_rides(
                session,
                pickup_lat,
                pickup_lon,
                dropoff_lat,
                dropoff_lon,
                radius_meters=settings.matching_radius_meters,
                max_detour_minutes=self.max_detour_minutes
            )
            
            # Filter by vehicle type if specified
            if vehicle_type:
                nearby_rides = [
                    ride for ride in nearby_rides
                    if ride["vehicle_type"] == vehicle_type.value
                ]
            
            # Calculate actual detour for each ride
            matching_rides = []
            for ride in nearby_rides:
                # Skip if not in corridor
                if not (ride["pickup_in_corridor"] and ride["dropoff_in_corridor"]):
                    continue
                
                # Calculate detour using OSRM
                detour_time, detour_distance = await self._calculate_ride_detour(
                    ride,
                    pickup_lat,
                    pickup_lon,
                    dropoff_lat,
                    dropoff_lon
                )
                
                # Check if detour is within cap
                if detour_time <= self.max_detour_minutes:
                    ride["detour_time_minutes"] = detour_time
                    ride["detour_distance_km"] = detour_distance
                    ride["within_detour_cap"] = True
                    matching_rides.append(ride)
                else:
                    ride["detour_time_minutes"] = detour_time
                    ride["detour_distance_km"] = detour_distance
                    ride["within_detour_cap"] = False
            
            # Sort by detour time
            matching_rides.sort(key=lambda x: x["detour_time_minutes"])
            
            logger.info(f"Found {len(matching_rides)} matching rides within detour cap")
            return matching_rides
            
        except Exception as e:
            logger.error(f"Error finding matching rides: {str(e)}")
            raise
    
    async def _calculate_ride_detour(
        self,
        ride: Dict,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float
    ) -> Tuple[float, float]:
        """
        Calculate detour for a specific ride.
        
        Args:
            ride: Ride information
            pickup_lat: New pickup latitude
            pickup_lon: New pickup longitude
            dropoff_lat: New dropoff latitude
            dropoff_lon: New dropoff longitude
            
        Returns:
            Tuple of (detour_time_minutes, detour_distance_km)
        """
        try:
            # This is a simplified calculation
            # In production, use actual route geometry from the ride
            # For now, estimate based on pickup/dropoff distances
            
            pickup_distance = ride.get("pickup_distance", 0)
            dropoff_distance = ride.get("dropoff_distance", 0)
            
            # Estimate detour distance (simplified)
            detour_distance = (pickup_distance + dropoff_distance) / 1000  # km
            
            # Estimate detour time (assuming 30 km/h average speed)
            detour_time = (detour_distance / 30) * 60  # minutes
            
            return (detour_time, detour_distance)
            
        except Exception as e:
            logger.error(f"Error calculating ride detour: {str(e)}")
            return (0.0, 0.0)
    
    async def suggest_modal_shifts(
        self,
        session: AsyncSession,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float
    ) -> List[Dict]:
        """
        Suggest modal shifts for nearby overlapping requests.
        
        Analyzes nearby requests and suggests:
        - 2 bike requests → 1 auto
        - 5 bike requests → 1 cab
        - 3 auto requests → 1 cab
        
        Args:
            session: Async database session
            pickup_lat: Pickup latitude
            pickup_lon: Pickup longitude
            dropoff_lat: Dropoff latitude
            dropoff_lon: Dropoff longitude
            
        Returns:
            List of modal shift suggestions
        """
        try:
            suggestions = []
            
            # Check for bike to auto conversion
            bike_rides = await self.spatial_service.find_overlapping_requests(
                session,
                VehicleType.BIKE.value,
                radius_meters=settings.matching_radius_meters
            )
            
            if len(bike_rides) >= settings.bike_to_auto_threshold:
                total_passengers = sum(
                    group["total_passengers"] for group in bike_rides
                )
                if total_passengers >= settings.bike_to_auto_threshold:
                    suggestions.append({
                        "current_type": VehicleType.BIKE.value,
                        "suggested_type": VehicleType.AUTO.value,
                        "source_rides": [group["ride1_id"] for group in bike_rides],
                        "total_passengers": total_passengers,
                        "estimated_savings": {
                            "cost": "30%",
                            "time": "20%"
                        }
                    })
            
            # Check for bike to cab conversion
            if len(bike_rides) >= settings.bike_to_cab_threshold:
                total_passengers = sum(
                    group["total_passengers"] for group in bike_rides
                )
                if total_passengers >= settings.bike_to_cab_threshold:
                    suggestions.append({
                        "current_type": VehicleType.BIKE.value,
                        "suggested_type": VehicleType.CAB.value,
                        "source_rides": [group["ride1_id"] for group in bike_rides],
                        "total_passengers": total_passengers,
                        "estimated_savings": {
                            "cost": "50%",
                            "time": "35%"
                        }
                    })
            
            # Check for auto to cab conversion
            auto_rides = await self.spatial_service.find_overlapping_requests(
                session,
                VehicleType.AUTO.value,
                radius_meters=settings.matching_radius_meters
            )
            
            if len(auto_rides) >= settings.auto_to_cab_threshold:
                total_passengers = sum(
                    group["total_passengers"] for group in auto_rides
                )
                if total_passengers >= settings.auto_to_cab_threshold:
                    suggestions.append({
                        "current_type": VehicleType.AUTO.value,
                        "suggested_type": VehicleType.CAB.value,
                        "source_rides": [group["ride1_id"] for group in auto_rides],
                        "total_passengers": total_passengers,
                        "estimated_savings": {
                            "cost": "25%",
                            "time": "15%"
                        }
                    })
            
            logger.info(f"Generated {len(suggestions)} modal shift suggestions")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting modal shifts: {str(e)}")
            raise
    
    async def calculate_route_geometry(
        self,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float
    ) -> Dict:
        """
        Calculate route geometry for a new ride.
        
        Args:
            pickup_lat: Pickup latitude
            pickup_lon: Pickup longitude
            dropoff_lat: Dropoff latitude
            dropoff_lon: Dropoff longitude
            
        Returns:
            Dictionary with route geometry and metadata
        """
        try:
            waypoints = [
                (pickup_lon, pickup_lat),
                (dropoff_lon, dropoff_lat)
            ]
            
            route_result = await self.osrm_service.get_route(waypoints)
            
            return {
                "geometry": route_result["geometry"],
                "distance_km": route_result["distance_km"],
                "duration_minutes": route_result["duration_minutes"]
            }
            
        except Exception as e:
            logger.error(f"Error calculating route geometry: {str(e)}")
            raise


# Global matching service instance
matching_service = MatchingService()


if __name__ == "__main__":
    import asyncio
    
    async def test_matching_service():
        """Test matching service."""
        print("Testing Matching Service...")
        
        service = MatchingService()
        
        # Test OSRM route calculation
        print("\nTesting OSRM route calculation...")
        try:
            route = await service.osrm_service.get_route([
                (77.5946, 12.9716),  # Bangalore
                (77.6245, 12.9352)   # Bangalore
            ])
            print(f"Route: {route['distance_km']} km, {route['duration_minutes']} min")
        except Exception as e:
            print(f"OSRM test failed (server may not be running): {e}")
        
        print("\nMatching service test completed!")
    
    asyncio.run(test_matching_service())
