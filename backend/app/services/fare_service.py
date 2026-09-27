"""
Dynamic Fare Calculation & Split-Payment Engine Service

This module implements:
- Dynamic fare calculation based on distance, time, and vehicle type
- Surge pricing with configurable multipliers
- Detour surcharge distribution among passengers
- Ride splitting and fare allocation
- Platform fee calculation

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from app.core.config import get_settings
from app.db.models import VehicleType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class SurgeLevel(str, Enum):
    """Surge pricing level enumeration."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class FareBreakdown:
    """Detailed fare breakdown."""
    base_fare: float
    distance_fare: float
    time_fare: float
    surge_multiplier: float
    surge_amount: float
    detour_surcharge: float
    platform_fee: float
    subtotal: float
    total_fare: float
    currency: str = "INR"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "base_fare": self.base_fare,
            "distance_fare": self.distance_fare,
            "time_fare": self.time_fare,
            "surge_multiplier": self.surge_multiplier,
            "surge_amount": self.surge_amount,
            "detour_surcharge": self.detour_surcharge,
            "platform_fee": self.platform_fee,
            "subtotal": self.subtotal,
            "total_fare": self.total_fare,
            "currency": self.currency
        }


@dataclass
class SplitFareAllocation:
    """Fare allocation for split rides."""
    passenger_id: int
    passenger_name: str
    share_percentage: float
    share_amount: float
    is_primary: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "passenger_id": self.passenger_id,
            "passenger_name": self.passenger_name,
            "share_percentage": self.share_percentage,
            "share_amount": self.share_amount,
            "is_primary": self.is_primary
        }


class FareService:
    """
    Dynamic fare calculation and split-payment engine.
    
    Provides:
    - Base fare calculation by vehicle type
    - Distance and time-based pricing
    - Surge pricing with configurable multipliers
    - Detour surcharge calculation
    - Ride splitting and fare allocation
    - Platform fee calculation
    """
    
    def __init__(self):
        """Initialize fare service."""
        self.base_fares = {
            VehicleType.BIKE: settings.base_fare_bike,
            VehicleType.AUTO: settings.base_fare_auto,
            VehicleType.CAB: settings.base_fare_cab
        }
        
        self.per_km_rates = {
            VehicleType.BIKE: settings.per_km_rate_bike,
            VehicleType.AUTO: settings.per_km_rate_auto,
            VehicleType.CAB: settings.per_km_rate_cab
        }
        
        self.surge_multipliers = {
            SurgeLevel.NONE: 1.0,
            SurgeLevel.LOW: 1.2,
            SurgeLevel.MEDIUM: 1.5,
            SurgeLevel.HIGH: 1.8,
            SurgeLevel.EXTREME: 2.0
        }
    
    def calculate_fare(
        self,
        vehicle_type: VehicleType,
        distance_km: float,
        duration_minutes: float,
        surge_level: SurgeLevel = SurgeLevel.NONE,
        detour_minutes: float = 0.0,
        apply_surge_cap: bool = True
    ) -> FareBreakdown:
        """
        Calculate dynamic fare for a ride.
        
        Args:
            vehicle_type: Type of vehicle
            distance_km: Distance in kilometers
            duration_minutes: Duration in minutes
            surge_level: Current surge level
            detour_minutes: Detour time in minutes
            apply_surge_cap: Whether to apply surge multiplier cap
            
        Returns:
            FareBreakdown with detailed fare components
        """
        # Base fare
        base_fare = self.base_fares[vehicle_type]
        
        # Distance fare
        distance_fare = distance_km * self.per_km_rates[vehicle_type]
        
        # Time fare
        time_fare = duration_minutes * settings.per_minute_rate
        
        # Subtotal before surge
        subtotal = base_fare + distance_fare + time_fare
        
        # Surge pricing
        surge_multiplier = self.surge_multipliers[surge_level]
        if apply_surge_cap:
            surge_multiplier = min(surge_multiplier, settings.surge_max_multiplier)
        
        surge_amount = subtotal * (surge_multiplier - 1)
        subtotal_with_surge = subtotal + surge_amount
        
        # Detour surcharge
        detour_surcharge = detour_minutes * settings.detour_surcharge_per_minute
        
        # Subtotal with detour
        subtotal_with_detour = subtotal_with_surge + detour_surcharge
        
        # Platform fee
        platform_fee = subtotal_with_detour * (settings.platform_fee_percent / 100)
        
        # Total fare
        total_fare = subtotal_with_detour + platform_fee
        
        return FareBreakdown(
            base_fare=base_fare,
            distance_fare=distance_fare,
            time_fare=time_fare,
            surge_multiplier=surge_multiplier,
            surge_amount=surge_amount,
            detour_surcharge=detour_surcharge,
            platform_fee=platform_fee,
            subtotal=subtotal_with_detour,
            total_fare=total_fare
        )
    
    def calculate_split_fare(
        self,
        total_fare: float,
        passengers: List[Dict],
        split_method: str = "equal"
    ) -> List[SplitFareAllocation]:
        """
        Calculate fare split among passengers.
        
        Args:
            total_fare: Total fare to split
            passengers: List of passenger dicts with id, name, and optionally distance_share
            split_method: Split method (equal, distance, custom)
            
        Returns:
            List of SplitFareAllocation
        """
        allocations = []
        
        if split_method == "equal":
            # Equal split among all passengers
            share_per_passenger = total_fare / len(passengers)
            share_percentage = 100.0 / len(passengers)
            
            for i, passenger in enumerate(passengers):
                allocations.append(SplitFareAllocation(
                    passenger_id=passenger["id"],
                    passenger_name=passenger.get("name", f"Passenger {i+1}"),
                    share_percentage=share_percentage,
                    share_amount=share_per_passenger,
                    is_primary=passenger.get("is_primary", i == 0)
                ))
        
        elif split_method == "distance":
            # Split based on distance traveled by each passenger
            total_distance = sum(p.get("distance_share", 1.0) for p in passengers)
            
            for i, passenger in enumerate(passengers):
                distance_share = passenger.get("distance_share", 1.0)
                share_percentage = (distance_share / total_distance) * 100
                share_amount = total_fare * (distance_share / total_distance)
                
                allocations.append(SplitFareAllocation(
                    passenger_id=passenger["id"],
                    passenger_name=passenger.get("name", f"Passenger {i+1}"),
                    share_percentage=share_percentage,
                    share_amount=share_amount,
                    is_primary=passenger.get("is_primary", i == 0)
                ))
        
        elif split_method == "custom":
            # Custom split based on provided percentages
            for i, passenger in enumerate(passengers):
                share_percentage = passenger.get("share_percentage", 0)
                share_amount = total_fare * (share_percentage / 100)
                
                allocations.append(SplitFareAllocation(
                    passenger_id=passenger["id"],
                    passenger_name=passenger.get("name", f"Passenger {i+1}"),
                    share_percentage=share_percentage,
                    share_amount=share_amount,
                    is_primary=passenger.get("is_primary", i == 0)
                ))
        
        else:
            raise ValueError(f"Unknown split method: {split_method}")
        
        return allocations
    
    def estimate_fare(
        self,
        vehicle_type: VehicleType,
        pickup_lat: float,
        pickup_lon: float,
        dropoff_lat: float,
        dropoff_lon: float,
        estimated_distance_km: float = None,
        estimated_duration_minutes: float = None
    ) -> Dict:
        """
        Estimate fare for a ride (without surge).
        
        Args:
            vehicle_type: Type of vehicle
            pickup_lat: Pickup latitude
            pickup_lon: Pickup longitude
            dropoff_lat: Dropoff latitude
            dropoff_lon: Dropoff longitude
            estimated_distance_km: Estimated distance (optional)
            estimated_duration_minutes: Estimated duration (optional)
            
        Returns:
            Dict with fare estimate
        """
        # If estimates not provided, use simple Haversine calculation
        if estimated_distance_km is None:
            estimated_distance_km = self._haversine_distance(
                pickup_lat, pickup_lon, dropoff_lat, dropoff_lon
            )
        
        if estimated_duration_minutes is None:
            # Estimate duration based on average speed (30 km/h)
            estimated_duration_minutes = (estimated_distance_km / 30) * 60
        
        # Calculate fare without surge
        fare = self.calculate_fare(
            vehicle_type=vehicle_type,
            distance_km=estimated_distance_km,
            duration_minutes=estimated_duration_minutes,
            surge_level=SurgeLevel.NONE,
            detour_minutes=0.0
        )
        
        # Calculate fare with different surge levels for display
        fare_estimates = {
            "none": self.calculate_fare(
                vehicle_type, estimated_distance_km, estimated_duration_minutes,
                SurgeLevel.NONE, 0.0
            ).total_fare,
            "low": self.calculate_fare(
                vehicle_type, estimated_distance_km, estimated_duration_minutes,
                SurgeLevel.LOW, 0.0
            ).total_fare,
            "medium": self.calculate_fare(
                vehicle_type, estimated_distance_km, estimated_duration_minutes,
                SurgeLevel.MEDIUM, 0.0
            ).total_fare,
            "high": self.calculate_fare(
                vehicle_type, estimated_distance_km, estimated_duration_minutes,
                SurgeLevel.HIGH, 0.0
            ).total_fare
        }
        
        return {
            "vehicle_type": vehicle_type.value,
            "distance_km": round(estimated_distance_km, 2),
            "duration_minutes": round(estimated_duration_minutes, 2),
            "base_fare": fare.to_dict(),
            "fare_estimates_by_surge": fare_estimates,
            "currency": "INR"
        }
    
    def calculate_detour_surcharge(
        self,
        original_fare: float,
        detour_minutes: float,
        num_passengers: int = 1
    ) -> Dict:
        """
        Calculate detour surcharge and distribute among passengers.
        
        Args:
            original_fare: Original fare without detour
            detour_minutes: Detour time in minutes
            num_passengers: Number of passengers to split surcharge
            
        Returns:
            Dict with surcharge breakdown
        """
        total_surcharge = detour_minutes * settings.detour_surcharge_per_minute
        surcharge_per_passenger = total_surcharge / num_passengers
        
        return {
            "detour_minutes": detour_minutes,
            "total_surcharge": total_surcharge,
            "surcharge_per_passenger": surcharge_per_passenger,
            "num_passengers": num_passengers,
            "currency": "INR"
        }
    
    def determine_surge_level(
        self,
        demand_factor: float,
        supply_factor: float,
        time_of_day: datetime = None
    ) -> SurgeLevel:
        """
        Determine surge level based on demand/supply factors.
        
        Args:
            demand_factor: Demand factor (0.0 to 2.0, where 1.0 is normal)
            supply_factor: Supply factor (0.0 to 2.0, where 1.0 is normal)
            time_of_day: Current time for time-based surge
            
        Returns:
            SurgeLevel
        """
        # Calculate demand/supply ratio
        if supply_factor > 0:
            ratio = demand_factor / supply_factor
        else:
            ratio = 2.0  # Max surge if no supply
        
        # Time-based surge (peak hours)
        if time_of_day:
            hour = time_of_day.hour
            if (7 <= hour <= 9) or (17 <= hour <= 19):
                ratio *= 1.3  # Peak hour multiplier
        
        # Determine surge level
        if ratio < 1.2:
            return SurgeLevel.NONE
        elif ratio < 1.5:
            return SurgeLevel.LOW
        elif ratio < 1.8:
            return SurgeLevel.MEDIUM
        elif ratio < 2.0:
            return SurgeLevel.HIGH
        else:
            return SurgeLevel.EXTREME
    
    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate Haversine distance between two points.
        
        Args:
            lat1: Latitude of point 1
            lon1: Longitude of point 1
            lat2: Latitude of point 2
            lon2: Longitude of point 2
            
        Returns:
            Distance in kilometers
        """
        from math import radians, cos, sin, sqrt, asin
        
        R = 6371  # Earth radius in km
        
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        return R * c


# Global fare service instance
fare_service = FareService()


if __name__ == "__main__":
    # Test fare service
    print("Testing Fare Service...")
    
    service = FareService()
    
    # Test fare calculation
    fare = service.calculate_fare(
        vehicle_type=VehicleType.CAB,
        distance_km=10.5,
        duration_minutes=25,
        surge_level=SurgeLevel.MEDIUM,
        detour_minutes=3
    )
    
    print(f"\nFare Breakdown:")
    print(f"Base Fare: ₹{fare.base_fare}")
    print(f"Distance Fare: ₹{fare.distance_fare}")
    print(f"Time Fare: ₹{fare.time_fare}")
    print(f"Surge Multiplier: {fare.surge_multiplier}x")
    print(f"Surge Amount: ₹{fare.surge_amount}")
    print(f"Detour Surcharge: ₹{fare.detour_surcharge}")
    print(f"Platform Fee: ₹{fare.platform_fee}")
    print(f"Total Fare: ₹{fare.total_fare}")
    
    # Test split fare
    passengers = [
        {"id": 1, "name": "Alice", "is_primary": True},
        {"id": 2, "name": "Bob", "is_primary": False}
    ]
    
    allocations = service.calculate_split_fare(fare.total_fare, passengers, "equal")
    
    print(f"\nFare Split (Equal):")
    for alloc in allocations:
        print(f"{alloc.passenger_name}: ₹{alloc.share_amount} ({alloc.share_percentage:.1f}%)")
    
    # Test fare estimate
    estimate = service.estimate_fare(
        vehicle_type=VehicleType.AUTO,
        pickup_lat=12.9716,
        pickup_lon=77.5946,
        dropoff_lat=12.9352,
        dropoff_lon=77.6245
    )
    
    print(f"\nFare Estimate:")
    print(f"Distance: {estimate['distance_km']} km")
    print(f"Duration: {estimate['duration_minutes']} min")
    print(f"Base Fare: ₹{estimate['base_fare']['total_fare']}")
    print(f"With Low Surge: ₹{estimate['fare_estimates_by_surge']['low']}")
    print(f"With High Surge: ₹{estimate['fare_estimates_by_surge']['high']}")
    
    print("\nFare service test completed!")
