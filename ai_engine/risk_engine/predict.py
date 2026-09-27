"""
Ultra-Fast ONNX Runtime Inference Engine for Risk Prediction

This module implements:
- UltraFastRiskPredictor class using ONNX Runtime for sub-5ms latency
- Structured JSON response with risk level, confidence, uncertainty flags
- Action protocol recommendations based on risk level
- High-performance inference with preallocated tensors

Author: OptimalRide AI Team
Date: 2026-09-27
"""

import numpy as np
import onnxruntime as ort
import json
import time
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import joblib
import os

# Import feature engineering pipeline
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from feature_engineering import RiskFeaturePipeline


class UltraFastRiskPredictor:
    """
    Ultra-fast risk predictor using ONNX Runtime for sub-5ms inference.
    
    Features:
    - ONNX Runtime with optimized execution providers
    - Preallocated tensors for zero-copy inference
    - Structured JSON response with action protocols
    - Uncertainty estimation integration
    """
    
    RISK_CLASSES = ['Green', 'Yellow', 'Red']
    RISK_CODES = [0, 1, 2]
    
    ACTION_PROTOCOLS = {
        'Green': {
            'dispatch_mode': 'Standard Dispatch',
            'otp_level': 'Normal OTP',
            'tracking': 'Standard',
            'verification': 'None',
            'emergency_alert': 'Standby'
        },
        'Yellow': {
            'dispatch_mode': 'Standard Dispatch',
            'otp_level': 'Enhanced OTP',
            'tracking': 'Active Route Tracking',
            'verification': 'Mid-route Driver Face Verification',
            'emergency_alert': 'Standby'
        },
        'Red': {
            'dispatch_mode': 'Block Auto-Dispatch',
            'otp_level': 'Mandatory Biometric OTP',
            'tracking': 'Continuous GPS Tracking',
            'verification': 'Mandatory Biometric Scan',
            'emergency_alert': 'Emergency Alert Ready'
        }
    }
    
    def __init__(
        self,
        onnx_model_path: str,
        scaler_path: str,
        uncertainty_estimator_path: Optional[str] = None,
        execution_providers: Optional[List[str]] = None
    ):
        """
        Initialize the ultra-fast risk predictor.
        
        Args:
            onnx_model_path: Path to ONNX model file
            scaler_path: Path to feature scaler
            uncertainty_estimator_path: Path to uncertainty estimator (optional)
            execution_providers: ONNX Runtime execution providers (e.g., ['CUDAExecutionProvider', 'CPUExecutionProvider'])
        """
        self.onnx_model_path = onnx_model_path
        self.scaler_path = scaler_path
        self.uncertainty_estimator_path = uncertainty_estimator_path
        
        # Set default execution providers
        if execution_providers is None:
            execution_providers = ['CPUExecutionProvider']
        
        print(f"Loading ONNX model from: {onnx_model_path}")
        print(f"Using execution providers: {execution_providers}")
        
        # Load ONNX model
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.intra_op_num_threads = 1
        
        self.ort_session = ort.InferenceSession(
            onnx_model_path,
            sess_options=so,
            providers=execution_providers
        )
        
        # Get input/output info
        self.input_name = self.ort_session.get_inputs()[0].name
        self.input_shape = self.ort_session.get_inputs()[0].shape
        self.output_names = [output.name for output in self.ort_session.get_outputs()]
        
        print(f"Model loaded successfully")
        print(f"Input shape: {self.input_shape}")
        print(f"Output names: {self.output_names}")
        
        # Load feature pipeline and scaler
        self.feature_pipeline = RiskFeaturePipeline(scaler_path=scaler_path)
        
        # Load uncertainty estimator if available
        self.uncertainty_estimator = None
        if uncertainty_estimator_path and os.path.exists(uncertainty_estimator_path):
            self.uncertainty_estimator = joblib.load(uncertainty_estimator_path)
            print(f"Uncertainty estimator loaded from: {uncertainty_estimator_path}")
        
        # Preallocate input tensor for zero-copy inference
        self.n_features = self.input_shape[1]
        self.input_tensor = np.zeros((1, self.n_features), dtype=np.float32)
        
        print("UltraFastRiskPredictor initialized successfully")
    
    def predict(
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
    ) -> Dict:
        """
        Perform ultra-fast risk prediction.
        
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
            Dictionary with prediction results
        """
        if co_passenger_verification_levels is None:
            co_passenger_verification_levels = []
        
        # Start timing
        start_time = time.perf_counter()
        
        # Extract features
        features = self.feature_pipeline.extract_all_features(
            timestamp=timestamp,
            road_segment_crime_index=road_segment_crime_index,
            lighting_density_score=lighting_density_score,
            route_isolation_factor=route_isolation_factor,
            distance_from_arterial=distance_from_arterial,
            driver_30day_rating=driver_30day_rating,
            driver_7day_rating=driver_7day_rating,
            completion_rate=completion_rate,
            harsh_braking_frequency=harsh_braking_frequency,
            speeding_frequency=speeding_frequency,
            total_rides_last_30days=total_rides_last_30days,
            passenger_verification_level=passenger_verification_level,
            passenger_trust_score=passenger_trust_score,
            co_passenger_count=co_passenger_count,
            co_passenger_verification_levels=co_passenger_verification_levels
        )
        
        # Normalize features
        normalized_features = self.feature_pipeline.normalize_features(features, fit=False)
        
        # Copy to preallocated tensor (zero-copy)
        self.input_tensor[0, :] = normalized_features.astype(np.float32)
        
        # Run ONNX inference
        ort_outputs = self.ort_session.run(
            self.output_names,
            {self.input_name: self.input_tensor}
        )
        
        # Get probabilities
        probabilities = ort_outputs[0][0]  # Shape: (3,)
        
        # Get prediction
        predicted_class_idx = int(np.argmax(probabilities))
        risk_level = self.RISK_CLASSES[predicted_class_idx]
        risk_code = self.RISK_CODES[predicted_class_idx]
        confidence_score = float(probabilities[predicted_class_idx])
        
        # Calculate uncertainty
        uncertainty_flag = False
        uncertainty_metrics = {}
        
        if self.uncertainty_estimator:
            uncertainty_metrics = self.uncertainty_estimator.predict_uncertainty(probabilities)
            uncertainty_flag = uncertainty_metrics['uncertainty_flag']
        else:
            # Fallback: calculate entropy directly
            eps = 1e-10
            clipped_probs = np.clip(probabilities, eps, 1 - eps)
            entropy = -np.sum(clipped_probs * np.log(clipped_probs))
            uncertainty_flag = entropy > 0.45
            uncertainty_metrics = {
                'entropy': float(entropy),
                'uncertainty_flag': uncertainty_flag,
                'threshold': 0.45
            }
        
        # Get action protocol
        action_protocol = self.ACTION_PROTOCOLS[risk_level].copy()
        
        # Apply uncertainty escalation
        if uncertainty_flag and risk_level == 'Green':
            risk_level = 'Yellow'
            risk_code = 1
            action_protocol = self.ACTION_PROTOCOLS['Yellow'].copy()
            action_protocol['escalation_reason'] = 'High uncertainty'
        elif uncertainty_flag and risk_level == 'Yellow':
            risk_level = 'Red'
            risk_code = 2
            action_protocol = self.ACTION_PROTOCOLS['Red'].copy()
            action_protocol['escalation_reason'] = 'High uncertainty'
        
        # End timing
        end_time = time.perf_counter()
        inference_time_ms = (end_time - start_time) * 1000
        
        # Build response
        response = {
            'risk_level': risk_level,
            'risk_code': risk_code,
            'confidence_score': confidence_score,
            'class_probabilities': {
                self.RISK_CLASSES[i]: float(probabilities[i])
                for i in range(len(self.RISK_CLASSES))
            },
            'uncertainty_flag': uncertainty_flag,
            'uncertainty_metrics': uncertainty_metrics,
            'inference_time_ms': float(inference_time_ms),
            'action_protocol': action_protocol,
            'features_summary': {
                'temporal_risk_score': features.get('is_late_night_window', 0.0),
                'spatial_risk_score': features.get('spatial_risk_composite', 0.0),
                'driver_reliability_score': features.get('driver_reliability_score', 0.0),
                'passenger_safety_index': features.get('passenger_safety_index', 0.0),
                'composite_risk_interaction': features.get('composite_risk_interaction', 0.0)
            }
        }
        
        return response
    
    def predict_batch(
        self,
        batch_data: List[Dict]
    ) -> List[Dict]:
        """
        Perform batch prediction for multiple requests.
        
        Args:
            batch_data: List of dictionaries containing input data for each prediction
            
        Returns:
            List of prediction results
        """
        results = []
        
        for data in batch_data:
            result = self.predict(
                timestamp=data['timestamp'],
                road_segment_crime_index=data['road_segment_crime_index'],
                lighting_density_score=data['lighting_density_score'],
                route_isolation_factor=data['route_isolation_factor'],
                distance_from_arterial=data['distance_from_arterial'],
                driver_30day_rating=data['driver_30day_rating'],
                driver_7day_rating=data['driver_7day_rating'],
                completion_rate=data['completion_rate'],
                harsh_braking_frequency=data['harsh_braking_frequency'],
                speeding_frequency=data['speeding_frequency'],
                total_rides_last_30days=data['total_rides_last_30days'],
                passenger_verification_level=data['passenger_verification_level'],
                passenger_trust_score=data['passenger_trust_score'],
                co_passenger_count=data.get('co_passenger_count', 0),
                co_passenger_verification_levels=data.get('co_passenger_verification_levels', [])
            )
            results.append(result)
        
        return results
    
    def benchmark_latency(
        self,
        n_iterations: int = 1000
    ) -> Dict[str, float]:
        """
        Benchmark inference latency.
        
        Args:
            n_iterations: Number of iterations for benchmarking
            
        Returns:
            Dictionary with latency metrics
        """
        print(f"Benchmarking inference latency ({n_iterations} iterations)...")
        
        # Create sample input
        sample_input = {
            'timestamp': datetime.now(),
            'road_segment_crime_index': 0.5,
            'lighting_density_score': 0.5,
            'route_isolation_factor': 0.5,
            'distance_from_arterial': 500.0,
            'driver_30day_rating': 4.5,
            'driver_7day_rating': 4.5,
            'completion_rate': 0.95,
            'harsh_braking_frequency': 2.0,
            'speeding_frequency': 1.5,
            'total_rides_last_30days': 150,
            'passenger_verification_level': 'standard',
            'passenger_trust_score': 0.8,
            'co_passenger_count': 0,
            'co_passenger_verification_levels': []
        }
        
        # Warm-up
        for _ in range(10):
            _ = self.predict(**sample_input)
        
        # Benchmark
        latencies = []
        for _ in range(n_iterations):
            start_time = time.perf_counter()
            _ = self.predict(**sample_input)
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)  # Convert to ms
        
        latencies = np.array(latencies)
        
        latency_metrics = {
            'mean_latency_ms': float(np.mean(latencies)),
            'median_latency_ms': float(np.median(latencies)),
            'p95_latency_ms': float(np.percentile(latencies, 95)),
            'p99_latency_ms': float(np.percentile(latencies, 99)),
            'min_latency_ms': float(np.min(latencies)),
            'max_latency_ms': float(np.max(latencies))
        }
        
        print(f"\n=== ONNX Runtime Inference Latency ===")
        print(f"Mean: {latency_metrics['mean_latency_ms']:.3f} ms")
        print(f"Median: {latency_metrics['median_latency_ms']:.3f} ms")
        print(f"P95: {latency_metrics['p95_latency_ms']:.3f} ms")
        print(f"P99: {latency_metrics['p99_latency_ms']:.3f} ms")
        
        return latency_metrics


def load_predictor(
    models_dir: str = "ai_engine/models",
    model_name: str = "risk_engine"
) -> UltraFastRiskPredictor:
    """
    Load the ultra-fast risk predictor with default paths.
    
    Args:
        models_dir: Directory containing model artifacts
        model_name: Name of the model
        
    Returns:
        Initialized UltraFastRiskPredictor instance
    """
    onnx_path = os.path.join(models_dir, f"{model_name}.onnx")
    scaler_path = os.path.join(models_dir, f"{model_name}_scaler.joblib")
    uncertainty_path = os.path.join(models_dir, f"{model_name}_uncertainty.joblib")
    
    return UltraFastRiskPredictor(
        onnx_model_path=onnx_path,
        scaler_path=scaler_path,
        uncertainty_estimator_path=uncertainty_path
    )


def main():
    """Main function to test the predictor."""
    print("=" * 60)
    print("Ultra-Fast Risk Predictor Test")
    print("=" * 60)
    
    # Check if model exists
    onnx_path = "ai_engine/models/risk_engine.onnx"
    scaler_path = "ai_engine/models/risk_engine_scaler.joblib"
    
    if not os.path.exists(onnx_path):
        print(f"\nError: ONNX model not found at {onnx_path}")
        print("Please run train_risk_model.py first to generate the model.")
        return
    
    if not os.path.exists(scaler_path):
        print(f"\nError: Scaler not found at {scaler_path}")
        print("Please run train_risk_model.py first to generate the scaler.")
        return
    
    # Load predictor
    print("\nLoading predictor...")
    predictor = load_predictor()
    
    # Test single prediction
    print("\nTesting single prediction...")
    result = predictor.predict(
        timestamp=datetime.now(),
        road_segment_crime_index=0.7,
        lighting_density_score=0.3,
        route_isolation_factor=0.8,
        distance_from_arterial=800.0,
        driver_30day_rating=4.2,
        driver_7day_rating=3.8,
        completion_rate=0.88,
        harsh_braking_frequency=4.5,
        speeding_frequency=3.2,
        total_rides_last_30days=45,
        passenger_verification_level='basic',
        passenger_trust_score=0.6,
        co_passenger_count=1,
        co_passenger_verification_levels=['none']
    )
    
    print("\nPrediction Result:")
    print(json.dumps(result, indent=2, default=str))
    
    # Benchmark latency
    print("\n" + "=" * 60)
    latency_metrics = predictor.benchmark_latency(n_iterations=1000)
    
    # Check if target latency achieved
    target_latency = 5.0  # 5ms target
    if latency_metrics['p95_latency_ms'] < target_latency:
        print(f"\n✓ Target latency ({target_latency}ms) achieved!")
        print(f"  P95 latency: {latency_metrics['p95_latency_ms']:.3f}ms")
    else:
        print(f"\n✗ Target latency ({target_latency}ms) not achieved")
        print(f"  P95 latency: {latency_metrics['p95_latency_ms']:.3f}ms")
    
    print("\n" + "=" * 60)
    print("Predictor test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
