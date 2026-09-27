"""
OptimalRide Liveness Detection Module

This module provides state-of-the-art liveness detection for driver authentication.
"""

from .face_landmarker import (
    FaceLandmarker,
    LandmarkExtractionResult,
    EyeLandmarks,
    HeadPoseLandmarks,
    FaceBoundingBox,
    DetectionStatus
)

from .passive_liveness import (
    PassiveLivenessDetector,
    LivenessVerificationResult,
    EyeBlinkResult,
    HeadPoseResult,
    SpoofDetectionResult,
    LivenessStatus
)

from .low_light_fallback import (
    LowLightFallbackHandler,
    LightAssessmentResult,
    EnhancementResult,
    FallbackAuthPayload,
    FallbackResult,
    LightCondition,
    FallbackMethod
)

__all__ = [
    # Face Landmarker
    'FaceLandmarker',
    'LandmarkExtractionResult',
    'EyeLandmarks',
    'HeadPoseLandmarks',
    'FaceBoundingBox',
    'DetectionStatus',
    
    # Passive Liveness
    'PassiveLivenessDetector',
    'LivenessVerificationResult',
    'EyeBlinkResult',
    'HeadPoseResult',
    'SpoofDetectionResult',
    'LivenessStatus',
    
    # Low Light Fallback
    'LowLightFallbackHandler',
    'LightAssessmentResult',
    'EnhancementResult',
    'FallbackAuthPayload',
    'FallbackResult',
    'LightCondition',
    'FallbackMethod'
]

__version__ = '1.0.0'
