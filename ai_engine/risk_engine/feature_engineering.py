"""
Advanced Multi-Modal Spatial-Temporal Feature Engineering Pipeline for OptimalRide Risk Engine

This module implements a comprehensive feature extraction pipeline combining:
- Temporal Dynamics (time of day, day of week, late night windows)
- Spatial Road Segment Embedding (crime index, lighting density, isolation factor)
- Driver Behavioral Anomaly (rating drift, completion rate, telemetry anomalies)
- Co-Passenger Safety Index (verification level, trust scores)
- Spatial-Temporal Interaction Terms

Author: OptimalRide AI Team
Date: 2026-09-27
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import joblib
import os


class TemporalFeatureExtractor:
    """Extract temporal dynamics features from timestamp data."""
    
    LATE_NIGHT_START = time(22, 0)  # 10 PM
    LATE_NIGHT_END = time(5, 0)     # 5 AM
    
    @staticmethod
    def extract_features(timestamp: datetime) -> Dict[str, float]:
        """
        Extract temporal features from a timestamp.
        
        Args:
            timestamp: Datetime object representing the ride request time
            
        Returns:
            Dictionary of temporal features
        """
        features = {}
        
        # Basic temporal features
        features['time_of_day'] = timestamp.hour + timestamp.minute / 60.0
        features['day_of_week'] = timestamp.weekday()  # 0=Monday, 6=Sunday
        features['is_weekend'] = 1.0 if timestamp.weekday() >= 5 else 0.0
        
        # Late night window detection (10 PM - 5 AM)
        current_time = timestamp.time()
        features['is_late_night_window'] = 1.0 if (
            current_time >= TemporalFeatureExtractor.LATE_NIGHT_START or 
            current_time <= TemporalFeatureExtractor.LATE_NIGHT_END
        ) else 0.0
        
        # Peak hours (7-9 AM, 5-7 PM)
        features['is_morning_peak'] = 1.0 if 7 <= timestamp.hour < 9 else 0.0
        features['is_evening_peak'] = 1.0 if 17 <= timestamp.hour < 19 else 0.0
        
        # Cyclical encoding for time of day
        features['time_sin'] = np.sin(2 * np.pi * features['time_of_day'] / 24.0)
        features['time_cos'] = np.cos(2 * np.pi * features['time_of_day'] / 24.0)
        
        # Cyclical encoding for day of week
        features['day_sin'] = np.sin(2 * np.pi * features['day_of_week'] / 7.0)
        features['day_cos'] = np.cos(2 * np.pi * features['day_of_week'] / 7.0)
        
        return features


class SpatialFeatureExtractor:
    """Extract spatial road segment embedding features."""
    
    @staticmethod
    def extract_features(
        road_segment_crime_index: float,
        lighting_density_score: float,
        route_isolation_factor: float,
        distance_from_arterial: float
    ) -> Dict[str, float]:
        """
        Extract spatial features from road segment data.
        
        Args:
            road_segment_crime_index: Normalized crime index (0-1)
            lighting_density_score: Lighting infrastructure score (0-1)
            route_isolation_factor: Distance from main arterial roads (0-1)
            distance_from_arterial: Actual distance in meters
            
        Returns:
            Dictionary of spatial features
        """
        features = {}
        
        # Direct spatial features
        features['road_segment_crime_index'] = float(road_segment_crime_index)
        features['lighting_density_score'] = float(lighting_density_score)
        features['route_isolation_factor'] = float(route_isolation_factor)
        features['distance_from_arterial_m'] = float(distance_from_arterial)
        
        # Derived spatial risk indicators
        features['poor_lighting_high_crime'] = (
            1.0 if lighting_density_score < 0.3 and road_segment_crime_index > 0.6 
            else 0.0
        )
        
        features['high_isolation_zone'] = 1.0 if route_isolation_factor > 0.7 else 0.0
        
        # Spatial risk composite score
        features['spatial_risk_composite'] = (
            road_segment_crime_index * 0.4 + 
            (1 - lighting_density_score) * 0.3 + 
            route_isolation_factor * 0.3
        )
        
        return features


class DriverBehaviorExtractor:
    """Extract driver behavioral anomaly features."""
    
    @staticmethod
    def extract_features(
        driver_30day_rating: float,
        driver_7day_rating: float,
        completion_rate: float,
        harsh_braking_frequency: float,
        speeding_frequency: float,
        total_rides_last_30days: int
    ) -> Dict[str, float]:
        """
        Extract driver behavioral features from historical data.
        
        Args:
            driver_30day_rating: Average rating over last 30 days
            driver_7day_rating: Average rating over last 7 days
            completion_rate: Ride completion rate (0-1)
            harsh_braking_frequency: Harsh braking events per 100km
            speeding_frequency: Speeding events per 100km
            total_rides_last_30days: Total rides completed in last 30 days
            
        Returns:
            Dictionary of driver behavior features
        """
        features = {}
        
        # Rating drift (30-day vs 7-day)
        features['driver_recent_rating_drift'] = driver_30day_rating - driver_7day_rating
        features['rating_declining'] = 1.0 if features['driver_recent_rating_drift'] > 0.2 else 0.0
        
        # Completion rate features
        features['completion_rate'] = float(completion_rate)
        features['low_completion_rate'] = 1.0 if completion_rate < 0.85 else 0.0
        
        # Telemetry anomaly scores
        features['harsh_braking_frequency'] = float(harsh_braking_frequency)
        features['speeding_frequency'] = float(speeding_frequency)
        features['telemetry_anomaly_score'] = (
            harsh_braking_frequency * 0.5 + speeding_frequency * 0.5
        )
        features['high_telemetry_anomaly'] = 1.0 if features['telemetry_anomaly_score'] > 5.0 else 0.0
        
        # Experience metrics
        features['total_rides_last_30days'] = float(total_rides_last_30days)
        features['is_inexperienced'] = 1.0 if total_rides_last_30days < 50 else 0.0
        
        # Driver reliability composite
        features['driver_reliability_score'] = (
            driver_7day_rating * 0.4 + 
            completion_rate * 0.4 + 
            (1 - min(features['telemetry_anomaly_score'] / 10.0, 1.0)) * 0.2
        )
        
        return features


class PassengerSafetyExtractor:
    """Extract co-passenger safety index features."""
    
    @staticmethod
    def extract_features(
        passenger_verification_level: str,
        passenger_trust_score: float,
        co_passenger_count: int,
        co_passenger_verification_levels: List[str]
    ) -> Dict[str, float]:
        """
        Extract passenger safety features from verification and trust data.
        
        Args:
            passenger_verification_level: Verification level of primary passenger
            passenger_trust_score: Trust score (0-1)
            co_passenger_count: Number of co-passengers
            co_passenger_verification_levels: List of verification levels for co-passengers
            
        Returns:
            Dictionary of passenger safety features
        """
        features = {}
        
        # Verification level encoding
        verification_mapping = {
            'none': 0.0,
            'basic': 0.33,
            'standard': 0.66,
            'enhanced': 1.0
        }
        
        primary_verification_score = verification_mapping.get(
            passenger_verification_level.lower(), 0.0
        )
        features['primary_verification_level'] = primary_verification_score
        
        # Trust score
        features['passenger_trust_score'] = float(passenger_trust_score)
        
        # Co-passenger features
        features['co_passenger_count'] = float(co_passenger_count)
        features['has_co_passengers'] = 1.0 if co_passenger_count > 0 else 0.0
        
        # Co-passenger verification composite
        if co_passenger_count > 0:
            co_verification_scores = [
                verification_mapping.get(level.lower(), 0.0) 
                for level in co_passenger_verification_levels
            ]
            features['co_passenger_avg_verification'] = np.mean(co_verification_scores)
            features['all_passengers_verified'] = (
                1.0 if all(score >= 0.66 for score in co_verification_scores) else 0.0
            )
        else:
            features['co_passenger_avg_verification'] = 0.0
            features['all_passengers_verified'] = 1.0
        
        # Overall passenger safety index
        features['passenger_safety_index'] = (
            primary_verification_score * 0.4 + 
            passenger_trust_score * 0.3 + 
            features['co_passenger_avg_verification'] * 0.3
        )
        
        return features


class SpatialTemporalInteractionEngine:
    """Engine for creating spatial-temporal interaction terms."""
    
    @staticmethod
    def create_interaction_features(
        temporal_features: Dict[str, float],
        spatial_features: Dict[str, float],
        driver_features: Dict[str, float],
        passenger_features: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Create high-order interaction features between different feature domains.
        
        Args:
            temporal_features: Dictionary of temporal features
            spatial_features: Dictionary of spatial features
            driver_features: Dictionary of driver behavior features
            passenger_features: Dictionary of passenger safety features
            
        Returns:
            Dictionary of interaction features
        """
        features = {}
        
        # Spatial-Temporal interactions
        features['isolation_late_night'] = (
            spatial_features['route_isolation_factor'] * 
            temporal_features['is_late_night_window']
        )
        
        features['crime_late_night'] = (
            spatial_features['road_segment_crime_index'] * 
            temporal_features['is_late_night_window']
        )
        
        features['poor_lighting_late_night'] = (
            (1 - spatial_features['lighting_density_score']) * 
            temporal_features['is_late_night_window']
        )
        
        # Driver-Spatial interactions
        features['inexperienced_high_crime'] = (
            driver_features['is_inexperienced'] * 
            spatial_features['road_segment_crime_index']
        )
        
        features['low_reliability_isolation'] = (
            (1 - driver_features['driver_reliability_score']) * 
            spatial_features['route_isolation_factor']
        )
        
        # Passenger-Spatial interactions
        features['low_verification_isolation'] = (
            (1 - passenger_features['passenger_safety_index']) * 
            spatial_features['route_isolation_factor']
        )
        
        # Driver-Temporal interactions
        features['rating_drift_late_night'] = (
            driver_features['rating_declining'] * 
            temporal_features['is_late_night_window']
        )
        
        features['telemetry_anomaly_peak_hours'] = (
            driver_features['high_telemetry_anomaly'] * 
            (temporal_features['is_morning_peak'] + temporal_features['is_evening_peak'])
        )
        
        # Composite risk interaction
        features['composite_risk_interaction'] = (
            spatial_features['spatial_risk_composite'] * 
            (1 - driver_features['driver_reliability_score']) * 
            (1 - passenger_features['passenger_safety_index']) * 
            (1 + temporal_features['is_late_night_window'])
        )
        
        return features


class RiskFeaturePipeline:
    """
    Main pipeline for extracting and transforming all risk features.
    Combines all feature extractors into a unified interface.
    """
    
    FEATURE_ORDER = [
        # Temporal features
        'time_of_day', 'day_of_week', 'is_weekend', 'is_late_night_window',
        'is_morning_peak', 'is_evening_peak', 'time_sin', 'time_cos',
        'day_sin', 'day_cos',
        
        # Spatial features
        'road_segment_crime_index', 'lighting_density_score', 'route_isolation_factor',
        'distance_from_arterial_m', 'poor_lighting_high_crime', 'high_isolation_zone',
        'spatial_risk_composite',
        
        # Driver behavior features
        'driver_recent_rating_drift', 'rating_declining', 'completion_rate',
        'low_completion_rate', 'harsh_braking_frequency', 'speeding_frequency',
        'telemetry_anomaly_score', 'high_telemetry_anomaly', 'total_rides_last_30days',
        'is_inexperienced', 'driver_reliability_score',
        
        # Passenger safety features
        'primary_verification_level', 'passenger_trust_score', 'co_passenger_count',
        'has_co_passengers', 'co_passenger_avg_verification', 'all_passengers_verified',
        'passenger_safety_index',
        
        # Interaction features
        'isolation_late_night', 'crime_late_night', 'poor_lighting_late_night',
        'inexperienced_high_crime', 'low_reliability_isolation',
        'low_verification_isolation', 'rating_drift_late_night',
        'telemetry_anomaly_peak_hours', 'composite_risk_interaction'
    ]
    
    def __init__(self, scaler_path: Optional[str] = None):
        """
        Initialize the feature pipeline.
        
        Args:
            scaler_path: Path to saved scaler for feature normalization
        """
        self.scaler = None
        if scaler_path and os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
        else:
            self.scaler = StandardScaler()
    
    def extract_all_features(
        self,
        # Temporal inputs
        timestamp: datetime,
        
        # Spatial inputs
        road_segment_crime_index: float,
        lighting_density_score: float,
        route_isolation_factor: float,
        distance_from_arterial: float,
        
        # Driver behavior inputs
        driver_30day_rating: float,
        driver_7day_rating: float,
        completion_rate: float,
        harsh_braking_frequency: float,
        speeding_frequency: float,
        total_rides_last_30days: int,
        
        # Passenger safety inputs
        passenger_verification_level: str,
        passenger_trust_score: float,
        co_passenger_count: int = 0,
        co_passenger_verification_levels: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Extract all features from raw inputs.
        
        Args:
            timestamp: Ride request timestamp
            road_segment_crime_index: Crime index for road segment
            lighting_density_score: Lighting infrastructure score
            route_isolation_factor: Distance from arterial roads
            distance_from_arterial: Actual distance in meters
            driver_30day_rating: 30-day average driver rating
            driver_7day_rating: 7-day average driver rating
            completion_rate: Driver completion rate
            harsh_braking_frequency: Harsh braking events per 100km
            speeding_frequency: Speeding events per 100km
            total_rides_last_30days: Total rides in last 30 days
            passenger_verification_level: Primary passenger verification level
            passenger_trust_score: Passenger trust score
            co_passenger_count: Number of co-passengers
            co_passenger_verification_levels: List of co-passenger verification levels
            
        Returns:
            Dictionary of all extracted features
        """
        if co_passenger_verification_levels is None:
            co_passenger_verification_levels = []
        
        # Extract features from each domain
        temporal_features = TemporalFeatureExtractor.extract_features(timestamp)
        spatial_features = SpatialFeatureExtractor.extract_features(
            road_segment_crime_index, lighting_density_score,
            route_isolation_factor, distance_from_arterial
        )
        driver_features = DriverBehaviorExtractor.extract_features(
            driver_30day_rating, driver_7day_rating, completion_rate,
            harsh_braking_frequency, speeding_frequency, total_rides_last_30days
        )
        passenger_features = PassengerSafetyExtractor.extract_features(
            passenger_verification_level, passenger_trust_score,
            co_passenger_count, co_passenger_verification_levels
        )
        
        # Create interaction features
        interaction_features = SpatialTemporalInteractionEngine.create_interaction_features(
            temporal_features, spatial_features, driver_features, passenger_features
        )
        
        # Combine all features
        all_features = {}
        all_features.update(temporal_features)
        all_features.update(spatial_features)
        all_features.update(driver_features)
        all_features.update(passenger_features)
        all_features.update(interaction_features)
        
        return all_features
    
    def normalize_features(
        self,
        features: Dict[str, float],
        fit: bool = False
    ) -> np.ndarray:
        """
        Normalize features using the fitted scaler.
        
        Args:
            features: Dictionary of features
            fit: Whether to fit the scaler on this data
            
        Returns:
            Normalized feature array
        """
        # Ensure features are in the correct order
        feature_array = np.array([features.get(feat, 0.0) for feat in self.FEATURE_ORDER])
        
        if fit:
            normalized = self.scaler.fit_transform(feature_array.reshape(1, -1))
        else:
            normalized = self.scaler.transform(feature_array.reshape(1, -1))
        
        return normalized.flatten()
    
    def save_scaler(self, path: str):
        """Save the fitted scaler to disk."""
        joblib.dump(self.scaler, path)
    
    def process_batch(
        self,
        data_rows: List[Dict],
        fit_scaler: bool = False
    ) -> np.ndarray:
        """
        Process a batch of data rows for training.
        
        Args:
            data_rows: List of dictionaries containing raw input data
            fit_scaler: Whether to fit the scaler on this batch
            
        Returns:
            2D array of normalized features
        """
        feature_matrix = []
        
        for row in data_rows:
            features = self.extract_all_features(
                timestamp=row['timestamp'],
                road_segment_crime_index=row['road_segment_crime_index'],
                lighting_density_score=row['lighting_density_score'],
                route_isolation_factor=row['route_isolation_factor'],
                distance_from_arterial=row['distance_from_arterial'],
                driver_30day_rating=row['driver_30day_rating'],
                driver_7day_rating=row['driver_7day_rating'],
                completion_rate=row['completion_rate'],
                harsh_braking_frequency=row['harsh_braking_frequency'],
                speeding_frequency=row['speeding_frequency'],
                total_rides_last_30days=row['total_rides_last_30days'],
                passenger_verification_level=row['passenger_verification_level'],
                passenger_trust_score=row['passenger_trust_score'],
                co_passenger_count=row.get('co_passenger_count', 0),
                co_passenger_verification_levels=row.get('co_passenger_verification_levels', [])
            )
            
            feature_array = np.array([features.get(feat, 0.0) for feat in self.FEATURE_ORDER])
            feature_matrix.append(feature_array)
        
        feature_matrix = np.array(feature_matrix)
        
        if fit_scaler:
            normalized = self.scaler.fit_transform(feature_matrix)
        else:
            normalized = self.scaler.transform(feature_matrix)
        
        return normalized


def create_sample_data(n_samples: int = 1000) -> pd.DataFrame:
    """
    Create synthetic sample data for testing the feature pipeline.
    
    Args:
        n_samples: Number of samples to generate
        
    Returns:
        DataFrame with sample data
    """
    np.random.seed(42)
    
    data = []
    for _ in range(n_samples):
        # Generate random timestamps within the last year
        timestamp = datetime.now() - pd.Timedelta(
            days=np.random.randint(0, 365),
            hours=np.random.randint(0, 24),
            minutes=np.random.randint(0, 60)
        )
        
        row = {
            'timestamp': timestamp,
            'road_segment_crime_index': np.random.uniform(0, 1),
            'lighting_density_score': np.random.uniform(0, 1),
            'route_isolation_factor': np.random.uniform(0, 1),
            'distance_from_arterial': np.random.uniform(0, 2000),
            'driver_30day_rating': np.random.uniform(3.0, 5.0),
            'driver_7day_rating': np.random.uniform(3.0, 5.0),
            'completion_rate': np.random.uniform(0.7, 1.0),
            'harsh_braking_frequency': np.random.uniform(0, 10),
            'speeding_frequency': np.random.uniform(0, 10),
            'total_rides_last_30days': np.random.randint(10, 500),
            'passenger_verification_level': np.random.choice(
                ['none', 'basic', 'standard', 'enhanced']
            ),
            'passenger_trust_score': np.random.uniform(0, 1),
            'co_passenger_count': np.random.randint(0, 3),
            'co_passenger_verification_levels': [
                np.random.choice(['none', 'basic', 'standard', 'enhanced'])
                for _ in range(np.random.randint(0, 3))
            ]
        }
        data.append(row)
    
    return pd.DataFrame(data)


if __name__ == "__main__":
    # Test the feature pipeline
    print("Testing Risk Feature Pipeline...")
    
    pipeline = RiskFeaturePipeline()
    
    # Test single feature extraction
    sample_features = pipeline.extract_all_features(
        timestamp=datetime.now(),
        road_segment_crime_index=0.6,
        lighting_density_score=0.4,
        route_isolation_factor=0.7,
        distance_from_arterial=500.0,
        driver_30day_rating=4.5,
        driver_7day_rating=4.2,
        completion_rate=0.95,
        harsh_braking_frequency=2.0,
        speeding_frequency=1.5,
        total_rides_last_30days=150,
        passenger_verification_level='standard',
        passenger_trust_score=0.8,
        co_passenger_count=1,
        co_passenger_verification_levels=['basic']
    )
    
    print(f"\nExtracted {len(sample_features)} features")
    print(f"Feature names: {list(sample_features.keys())}")
    
    # Test batch processing
    print("\nTesting batch processing...")
    sample_data = create_sample_data(100)
    feature_matrix = pipeline.process_batch(sample_rows=sample_data.to_dict('records'), fit_scaler=True)
    
    print(f"Processed {feature_matrix.shape[0]} samples with {feature_matrix.shape[1]} features")
    
    # Save scaler
    scaler_path = "ai_engine/risk_engine/datasets/feature_scaler.joblib"
    os.makedirs(os.path.dirname(scaler_path), exist_ok=True)
    pipeline.save_scaler(scaler_path)
    print(f"\nScaler saved to {scaler_path}")
    
    print("\nFeature pipeline test completed successfully!")
