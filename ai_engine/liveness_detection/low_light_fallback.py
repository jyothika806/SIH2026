"""
Low-Light Detection & Biometric Fallback System

This module implements:
- Ambient light level calculation using mean pixel intensity
- Contrast Limited Adaptive Histogram Equalization (CLAHE) for low-light enhancement
- Frame quality assessment after enhancement
- Biometric fallback trigger for device-native authentication (Fingerprint/FaceID)
- Infrared sensor pipeline integration

Author: OptimalRide AI Team
Date: 2026-09-27
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Union
from dataclasses import dataclass
from enum import Enum
import logging
import json
from datetime import datetime, timedelta
import secrets
import string

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightCondition(Enum):
    """Light condition classification."""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"
    INSUFFICIENT = "insufficient"


class FallbackMethod(Enum):
    """Available fallback authentication methods."""
    DEVICE_FINGERPRINT = "device_fingerprint"
    DEVICE_FACEID = "device_faceid"
    INFRARED_SENSOR = "infrared_sensor"
    MANUAL_VERIFICATION = "manual_verification"


@dataclass
class LightAssessmentResult:
    """Result of light condition assessment."""
    mean_brightness: float
    light_condition: LightCondition
    is_low_light: bool
    brightness_threshold: float
    clahe_required: bool
    enhancement_needed: bool


@dataclass
class EnhancementResult:
    """Result of image enhancement."""
    enhanced_image: np.ndarray
    brightness_improvement: float
    contrast_improvement: float
    quality_score: float
    enhancement_successful: bool
    quality_sufficient: bool


@dataclass
class FallbackAuthPayload:
    """Payload for fallback authentication."""
    fallback_method: FallbackMethod
    auth_token: str
    expires_at: datetime
    verification_required: bool
    device_capabilities: Dict[str, bool]
    infrared_available: bool
    fallback_reason: str


@dataclass
class FallbackResult:
    """Result of fallback authentication process."""
    fallback_triggered: bool
    fallback_method: Optional[FallbackMethod]
    auth_payload: Optional[FallbackAuthPayload]
    error_message: Optional[str] = None


class LowLightFallbackHandler:
    """
    Low-light detection and biometric fallback handler.
    
    Handles:
    - Light condition assessment
    - CLAHE-based image enhancement
    - Quality assessment after enhancement
    - Biometric fallback triggering
    """
    
    # Brightness thresholds (0-255 scale)
    BRIGHTNESS_THRESHOLDS = {
        LightCondition.INSUFFICIENT: 25,
        LightCondition.VERY_LOW: 40,
        LightCondition.LOW: 70,
        LightCondition.MODERATE: 120,
        LightCondition.GOOD: 180,
        LightCondition.EXCELLENT: 220
    }
    
    # CLAHE parameters
    CLAHE_CLIP_LIMIT = 2.0
    CLAHE_TILE_GRID_SIZE = (8, 8)
    
    # Quality thresholds
    MIN_QUALITY_SCORE = 0.6
    MIN_BRIGHTNESS_IMPROVEMENT = 20.0
    
    # Fallback authentication token validity
    TOKEN_VALIDITY_MINUTES = 15
    
    def __init__(
        self,
        brightness_threshold: float = 40.0,
        clahe_clip_limit: float = 2.0,
        min_quality_score: float = 0.6
    ):
        """
        Initialize the Low-Light Fallback Handler.
        
        Args:
            brightness_threshold: Brightness threshold for low-light detection
            clahe_clip_limit: CLAHE clip limit for contrast enhancement
            min_quality_score: Minimum quality score after enhancement
        """
        self.brightness_threshold = brightness_threshold
        self.clahe_clip_limit = clahe_clip_limit
        self.min_quality_score = min_quality_score
        
        # Initialize CLAHE
        self.clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip_limit,
            tileGridSize=self.CLAHE_TILE_GRID_SIZE
        )
        
        logger.info("LowLightFallbackHandler initialized successfully")
    
    def assess_light_condition(
        self,
        image: np.ndarray
    ) -> LightAssessmentResult:
        """
        Assess ambient light condition from image.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            LightAssessmentResult with light condition details
        """
        # Convert to grayscale for brightness calculation
        if len(image.shape) == 3:
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray_image = image
        
        # Calculate mean brightness
        mean_brightness = np.mean(gray_image)
        
        # Determine light condition
        light_condition = LightCondition.INSUFFICIENT
        for condition, threshold in sorted(
            self.BRIGHTNESS_THRESHOLDS.items(),
            key=lambda x: x[1]
        ):
            if mean_brightness >= threshold:
                light_condition = condition
        
        # Check if low light
        is_low_light = mean_brightness < self.brightness_threshold
        
        # Determine if CLAHE is required
        clahe_required = is_low_light and light_condition != LightCondition.INSUFFICIENT
        
        # Determine if enhancement is needed
        enhancement_needed = is_low_light
        
        return LightAssessmentResult(
            mean_brightness=float(mean_brightness),
            light_condition=light_condition,
            is_low_light=is_low_light,
            brightness_threshold=self.brightness_threshold,
            clahe_required=clahe_required,
            enhancement_needed=enhancement_needed
        )
    
    def apply_clahe_enhancement(
        self,
        image: np.ndarray
    ) -> EnhancementResult:
        """
        Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for low-light enhancement.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            EnhancementResult with enhanced image and quality metrics
        """
        try:
            # Store original brightness
            original_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            original_brightness = np.mean(original_gray)
            
            # Convert to LAB color space for better enhancement
            lab_image = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            
            # Split LAB channels
            l_channel, a_channel, b_channel = cv2.split(lab_image)
            
            # Apply CLAHE to L channel (lightness)
            clahe = cv2.createCLAHE(
                clipLimit=self.clahe_clip_limit,
                tileGridSize=self.CLAHE_TILE_GRID_SIZE
            )
            enhanced_l = clahe.apply(l_channel)
            
            # Merge channels back
            enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
            
            # Convert back to BGR
            enhanced_image = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            # Calculate brightness improvement
            enhanced_gray = cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2GRAY)
            enhanced_brightness = np.mean(enhanced_gray)
            brightness_improvement = enhanced_brightness - original_brightness
            
            # Calculate contrast improvement (using standard deviation)
            original_contrast = np.std(original_gray)
            enhanced_contrast = np.std(enhanced_gray)
            contrast_improvement = enhanced_contrast - original_contrast
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(enhanced_image)
            
            # Check if quality is sufficient
            quality_sufficient = (
                quality_score >= self.min_quality_score and
                brightness_improvement >= self.MIN_BRIGHTNESS_IMPROVEMENT
            )
            
            return EnhancementResult(
                enhanced_image=enhanced_image,
                brightness_improvement=float(brightness_improvement),
                contrast_improvement=float(contrast_improvement),
                quality_score=float(quality_score),
                enhancement_successful=True,
                quality_sufficient=quality_sufficient
            )
            
        except Exception as e:
            logger.error(f"CLAHE enhancement failed: {str(e)}")
            return EnhancementResult(
                enhanced_image=image,
                brightness_improvement=0.0,
                contrast_improvement=0.0,
                quality_score=0.0,
                enhancement_successful=False,
                quality_sufficient=False
            )
    
    def _calculate_quality_score(self, image: np.ndarray) -> float:
        """
        Calculate overall image quality score.
        
        Args:
            image: Input image
            
        Returns:
            Quality score (0.0 to 1.0)
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Calculate Laplacian variance (sharpness)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Normalize sharpness score (0-100 is typical range)
        sharpness_score = min(laplacian_var / 100.0, 1.0)
        
        # Calculate brightness score (optimal around 128)
        mean_brightness = np.mean(gray)
        brightness_score = 1.0 - abs(mean_brightness - 128) / 128.0
        
        # Calculate contrast score (using standard deviation)
        contrast_score = min(np.std(gray) / 64.0, 1.0)
        
        # Combine scores with weights
        quality_score = (
            sharpness_score * 0.4 +
            brightness_score * 0.3 +
            contrast_score * 0.3
        )
        
        return quality_score
    
    def _generate_auth_token(self) -> str:
        """
        Generate a secure authentication token for fallback.
        
        Returns:
            Secure token string
        """
        # Generate cryptographically secure token
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        return token
    
    def fallback_to_secondary_biometric(
        self,
        device_capabilities: Optional[Dict[str, bool]] = None,
        infrared_available: bool = False,
        fallback_reason: str = "Low light conditions"
    ) -> FallbackResult:
        """
        Trigger fallback to secondary biometric authentication.
        
        Args:
            device_capabilities: Dictionary of device biometric capabilities
            infrared_available: Whether infrared sensor is available
            fallback_reason: Reason for fallback trigger
            
        Returns:
            FallbackResult with authentication payload
        """
        try:
            # Default device capabilities if not provided
            if device_capabilities is None:
                device_capabilities = {
                    'fingerprint': True,
                    'faceid': True,
                    'infrared': False
                }
            
            # Determine best fallback method
            fallback_method = self._select_fallback_method(
                device_capabilities,
                infrared_available
            )
            
            # Generate authentication token
            auth_token = self._generate_auth_token()
            
            # Set token expiration
            expires_at = datetime.now() + timedelta(
                minutes=self.TOKEN_VALIDITY_MINUTES
            )
            
            # Create auth payload
            auth_payload = FallbackAuthPayload(
                fallback_method=fallback_method,
                auth_token=auth_token,
                expires_at=expires_at,
                verification_required=True,
                device_capabilities=device_capabilities,
                infrared_available=infrared_available,
                fallback_reason=fallback_reason
            )
            
            logger.info(
                f"Fallback triggered: {fallback_method.value}, "
                f"Reason: {fallback_reason}"
            )
            
            return FallbackResult(
                fallback_triggered=True,
                fallback_method=fallback_method,
                auth_payload=auth_payload
            )
            
        except Exception as e:
            logger.error(f"Fallback authentication failed: {str(e)}")
            return FallbackResult(
                fallback_triggered=False,
                fallback_method=None,
                auth_payload=None,
                error_message=str(e)
            )
    
    def _select_fallback_method(
        self,
        device_capabilities: Dict[str, bool],
        infrared_available: bool
    ) -> FallbackMethod:
        """
        Select the best fallback authentication method based on device capabilities.
        
        Priority order:
        1. Infrared sensor (most secure for low light)
        2. Device FaceID (convenient and secure)
        3. Device Fingerprint (reliable fallback)
        4. Manual verification (last resort)
        
        Args:
            device_capabilities: Device biometric capabilities
            infrared_available: Infrared sensor availability
            
        Returns:
            Selected FallbackMethod
        """
        # Check infrared first (most secure for low light)
        if infrared_available or device_capabilities.get('infrared', False):
            return FallbackMethod.INFRARED_SENSOR
        
        # Check FaceID next
        if device_capabilities.get('faceid', False):
            return FallbackMethod.DEVICE_FACEID
        
        # Check fingerprint
        if device_capabilities.get('fingerprint', False):
            return FallbackMethod.DEVICE_FINGERPRINT
        
        # Fallback to manual verification
        return FallbackMethod.MANUAL_VERIFICATION
    
    def process_low_light_frame(
        self,
        image: np.ndarray,
        device_capabilities: Optional[Dict[str, bool]] = None,
        infrared_available: bool = False
    ) -> Tuple[LightAssessmentResult, Optional[EnhancementResult], Optional[FallbackResult]]:
        """
        Complete low-light frame processing pipeline.
        
        Args:
            image: Input image
            device_capabilities: Device biometric capabilities
            infrared_available: Infrared sensor availability
            
        Returns:
            Tuple of (light assessment, enhancement result, fallback result)
        """
        # Assess light condition
        light_assessment = self.assess_light_condition(image)
        
        enhancement_result = None
        fallback_result = None
        
        # If enhancement is needed and possible
        if light_assessment.enhancement_needed and light_assessment.clahe_required:
            enhancement_result = self.apply_clahe_enhancement(image)
            
            # If enhancement failed or quality is insufficient, trigger fallback
            if not enhancement_result.enhancement_successful or not enhancement_result.quality_sufficient:
                fallback_result = self.fallback_to_secondary_biometric(
                    device_capabilities=device_capabilities,
                    infrared_available=infrared_available,
                    fallback_reason="Image enhancement insufficient"
                )
        
        # If light condition is insufficient for any enhancement
        elif light_assessment.light_condition == LightCondition.INSUFFICIENT:
            fallback_result = self.fallback_to_secondary_biometric(
                device_capabilities=device_capabilities,
                infrared_available=infrared_available,
                fallback_reason="Insufficient light conditions"
            )
        
        return light_assessment, enhancement_result, fallback_result
    
    def auth_payload_to_dict(self, payload: FallbackAuthPayload) -> Dict:
        """
        Convert FallbackAuthPayload to dictionary for JSON serialization.
        
        Args:
            payload: FallbackAuthPayload object
            
        Returns:
            Dictionary representation
        """
        return {
            'fallback_method': payload.fallback_method.value,
            'auth_token': payload.auth_token,
            'expires_at': payload.expires_at.isoformat(),
            'verification_required': payload.verification_required,
            'device_capabilities': payload.device_capabilities,
            'infrared_available': payload.infrared_available,
            'fallback_reason': payload.fallback_reason
        }


def create_low_light_handler() -> LowLightFallbackHandler:
    """
    Factory function to create a configured LowLightFallbackHandler instance.
    
    Returns:
        Configured LowLightFallbackHandler instance
    """
    return LowLightFallbackHandler(
        brightness_threshold=40.0,
        clahe_clip_limit=2.0,
        min_quality_score=0.6
    )


if __name__ == "__main__":
    # Test the low-light fallback handler
    print("Testing LowLightFallbackHandler...")
    
    handler = create_low_light_handler()
    
    # Create test images with different light conditions
    print("\nTesting with bright image...")
    bright_image = np.ones((480, 640, 3), dtype=np.uint8) * 200
    light_assessment = handler.assess_light_condition(bright_image)
    print(f"Light condition: {light_assessment.light_condition}")
    print(f"Mean brightness: {light_assessment.mean_brightness:.2f}")
    print(f"Is low light: {light_assessment.is_low_light}")
    
    print("\nTesting with low-light image...")
    low_light_image = np.ones((480, 640, 3), dtype=np.uint8) * 30
    light_assessment = handler.assess_light_condition(low_light_image)
    print(f"Light condition: {light_assessment.light_condition}")
    print(f"Mean brightness: {light_assessment.mean_brightness:.2f}")
    print(f"Is low light: {light_assessment.is_low_light}")
    
    # Test CLAHE enhancement
    print("\nTesting CLAHE enhancement...")
    enhancement_result = handler.apply_clahe_enhancement(low_light_image)
    print(f"Enhancement successful: {enhancement_result.enhancement_successful}")
    print(f"Brightness improvement: {enhancement_result.brightness_improvement:.2f}")
    print(f"Quality score: {enhancement_result.quality_score:.2f}")
    print(f"Quality sufficient: {enhancement_result.quality_sufficient}")
    
    # Test fallback authentication
    print("\nTesting fallback authentication...")
    device_caps = {'fingerprint': True, 'faceid': True, 'infrared': False}
    fallback_result = handler.fallback_to_secondary_biometric(
        device_capabilities=device_caps,
        infrared_available=False,
        fallback_reason="Test fallback"
    )
    print(f"Fallback triggered: {fallback_result.fallback_triggered}")
    print(f"Fallback method: {fallback_result.fallback_method}")
    if fallback_result.auth_payload:
        print(f"Auth token: {fallback_result.auth_payload.auth_token[:8]}...")
    
    print("\nLowLightFallbackHandler test completed!")
