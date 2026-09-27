"""
3D Passive Liveness Detection Engine

This module implements:
- Eye Blink Detection using Eye Aspect Ratio (EAR)
- 3D Head Pose Estimation (Yaw, Pitch, Roll) using cv2.solvePnP
- Dynamic texture & depth variance checks for spoof detection
- Comprehensive liveness verification with confidence scoring

Author: OptimalRide AI Team
Date: 2026-09-27
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, List, Union
from dataclasses import dataclass
from enum import Enum
import logging

# Import face landmarker
try:
    from face_landmarker import (
        FaceLandmarker,
        LandmarkExtractionResult,
        EyeLandmarks,
        HeadPoseLandmarks,
        DetectionStatus
    )
except ImportError:
    # Handle relative import when run as module
    from .face_landmarker import (
        FaceLandmarker,
        LandmarkExtractionResult,
        EyeLandmarks,
        HeadPoseLandmarks,
        DetectionStatus
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LivenessStatus(Enum):
    """Status of liveness verification."""
    LIVE = "live"
    SPOOF_DETECTED = "spoof_detected"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass
class EyeBlinkResult:
    """Result of eye blink detection."""
    left_ear: float
    right_ear: float
    average_ear: float
    blink_detected: bool
    blink_threshold: float
    eyes_closed: bool


@dataclass
class HeadPoseResult:
    """Result of 3D head pose estimation."""
    yaw: float  # Left/right rotation
    pitch: float  # Up/down rotation
    roll: float  # Tilt rotation
    rotation_matrix: np.ndarray
    translation_vector: np.ndarray
    head_movement_valid: bool
    movement_threshold: Tuple[float, float, float]


@dataclass
class SpoofDetectionResult:
    """Result of spoof detection."""
    texture_variance: float
    depth_variance: float
    motion_score: float
    spoof_confidence: float
    is_spoof: bool
    spoof_indicators: List[str]


@dataclass
class LivenessVerificationResult:
    """Complete result of liveness verification."""
    is_live: bool
    blink_detected: bool
    head_movement_valid: bool
    spoof_confidence: float
    low_light_flag: bool
    confidence_score: float
    status: LivenessStatus
    eye_blink_result: Optional[EyeBlinkResult]
    head_pose_result: Optional[HeadPoseResult]
    spoof_result: Optional[SpoofDetectionResult]
    error_message: Optional[str] = None
    details: Dict = None


class PassiveLivenessDetector:
    """
    Passive liveness detection using 3D facial analysis.
    
    Implements challenge-free liveness detection through:
    - Eye blink detection (EAR)
    - 3D head pose estimation
    - Texture and depth analysis
    """
    
    # EAR thresholds for blink detection
    EAR_THRESHOLD = 0.21
    EAR_CONSEC_FRAMES = 2  # Consecutive frames below threshold
    
    # Head pose thresholds (in degrees)
    YAW_THRESHOLD = 30.0
    PITCH_THRESHOLD = 25.0
    ROLL_THRESHOLD = 20.0
    
    # Spoof detection thresholds
    TEXTURE_VARIANCE_THRESHOLD = 500.0
    DEPTH_VARIANCE_THRESHOLD = 0.05
    MOTION_THRESHOLD = 2.0
    
    def __init__(
        self,
        ear_threshold: float = 0.21,
        head_pose_thresholds: Tuple[float, float, float] = (30.0, 25.0, 20.0),
        spoof_threshold: float = 0.5
    ):
        """
        Initialize the Passive Liveness Detector.
        
        Args:
            ear_threshold: EAR threshold for blink detection
            head_pose_thresholds: (yaw, pitch, roll) thresholds in degrees
            spoof_threshold: Confidence threshold for spoof detection
        """
        self.ear_threshold = ear_threshold
        self.yaw_threshold, self.pitch_threshold, self.roll_threshold = head_pose_thresholds
        self.spoof_threshold = spoof_threshold
        
        # Initialize face landmarker
        self.face_landmarker = FaceLandmarker()
        
        # Frame counter for blink detection
        self.frame_counter = 0
        self.blink_frame_counter = 0
        
        # Camera matrix for head pose estimation
        self.focal_length = 640  # Will be adjusted based on image width
        self.camera_center = (320, 240)  # Will be adjusted based on image dimensions
        self.camera_matrix = None
        self.distortion_coeffs = np.zeros((4, 1))
        
        logger.info("PassiveLivenessDetector initialized successfully")
    
    def _calculate_ear(self, eye_landmarks: List[Tuple[float, float, float]]) -> float:
        """
        Calculate Eye Aspect Ratio (EAR) for blink detection.
        
        EAR formula:
        EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
        
        Args:
            eye_landmarks: 6 eye landmark points (p1-p6)
            
        Returns:
            Eye Aspect Ratio
        """
        # Extract coordinates
        p1 = np.array(eye_landmarks[0][:2])  # Horizontal extent
        p2 = np.array(eye_landmarks[1][:2])  # Top-left
        p3 = np.array(eye_landmarks[2][:2])  # Top-right
        p4 = np.array(eye_landmarks[3][:2])  # Horizontal extent
        p5 = np.array(eye_landmarks[4][:2])  # Bottom-right
        p6 = np.array(eye_landmarks[5][:2])  # Bottom-left
        
        # Calculate vertical distances
        vertical_1 = np.linalg.norm(p2 - p6)
        vertical_2 = np.linalg.norm(p3 - p5)
        
        # Calculate horizontal distance
        horizontal = np.linalg.norm(p1 - p4)
        
        # Calculate EAR
        ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
        
        return ear
    
    def detect_eye_blink(
        self,
        eye_landmarks: EyeLandmarks
    ) -> EyeBlinkResult:
        """
        Detect eye blink using Eye Aspect Ratio.
        
        Args:
            eye_landmarks: Eye landmarks from face landmarker
            
        Returns:
            EyeBlinkResult with blink detection status
        """
        # Calculate EAR for both eyes
        left_ear = self._calculate_ear(eye_landmarks.left_eye)
        right_ear = self._calculate_ear(eye_landmarks.right_eye)
        average_ear = (left_ear + right_ear) / 2.0
        
        # Check if eyes are closed (EAR below threshold)
        eyes_closed = average_ear < self.ear_threshold
        
        # Update frame counters
        if eyes_closed:
            self.blink_frame_counter += 1
        else:
            if self.blink_frame_counter >= self.EAR_CONSEC_FRAMES:
                # Blink detected
                blink_detected = True
            else:
                blink_detected = False
            self.blink_frame_counter = 0
        
        # If eyes are currently closed and we have enough consecutive frames
        if eyes_closed and self.blink_frame_counter >= self.EAR_CONSEC_FRAMES:
            blink_detected = True
        else:
            blink_detected = False
        
        return EyeBlinkResult(
            left_ear=left_ear,
            right_ear=right_ear,
            average_ear=average_ear,
            blink_detected=blink_detected,
            blink_threshold=self.ear_threshold,
            eyes_closed=eyes_closed
        )
    
    def _setup_camera_matrix(self, image_shape: Tuple[int, int]):
        """
        Setup camera matrix for head pose estimation.
        
        Args:
            image_shape: Image shape (height, width)
        """
        height, width = image_shape
        self.focal_length = width
        self.camera_center = (width // 2, height // 2)
        
        self.camera_matrix = np.array([
            [self.focal_length, 0, self.camera_center[0]],
            [0, self.focal_length, self.camera_center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
    
    def estimate_head_pose(
        self,
        head_pose_landmarks: HeadPoseLandmarks,
        image_shape: Tuple[int, int]
    ) -> HeadPoseResult:
        """
        Estimate 3D head pose using cv2.solvePnP.
        
        Args:
            head_pose_landmarks: Head pose landmarks from face landmarker
            image_shape: Image shape (height, width)
            
        Returns:
            HeadPoseResult with rotation angles and validity
        """
        # Setup camera matrix
        self._setup_camera_matrix(image_shape)
        
        # Get 2D image points from landmarks
        image_points = head_pose_landmarks.to_numpy()[:, :2]
        
        # Get 3D model points
        model_points = self.face_landmarker.MODEL_POINTS.copy()
        
        # Solve PnP
        success, rotation_vector, translation_vector = cv2.solvePnP(
            model_points,
            image_points,
            self.camera_matrix,
            self.distortion_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            logger.warning("solvePnP failed for head pose estimation")
            return HeadPoseResult(
                yaw=0.0,
                pitch=0.0,
                roll=0.0,
                rotation_matrix=np.eye(3),
                translation_vector=np.zeros(3),
                head_movement_valid=False,
                movement_threshold=(self.yaw_threshold, self.pitch_threshold, self.roll_threshold)
            )
        
        # Convert rotation vector to rotation matrix
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        
        # Calculate Euler angles (yaw, pitch, roll)
        # Using the rotation matrix to extract angles
        sy = np.sqrt(rotation_matrix[0, 0] * rotation_matrix[0, 0] + 
                     rotation_matrix[1, 0] * rotation_matrix[1, 0])
        
        singular = sy < 1e-6
        
        if not singular:
            pitch = np.arctan2(rotation_matrix[2, 0], sy)
            yaw = np.arctan2(-rotation_matrix[2, 1], rotation_matrix[2, 2])
            roll = np.arctan2(-rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            pitch = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            yaw = np.arctan2(-rotation_matrix[2, 1], rotation_matrix[2, 2])
            roll = 0.0
        
        # Convert to degrees
        pitch_deg = np.degrees(pitch)
        yaw_deg = np.degrees(yaw)
        roll_deg = np.degrees(roll)
        
        # Check if head movement is within valid range
        head_movement_valid = (
            abs(yaw_deg) < self.yaw_threshold and
            abs(pitch_deg) < self.pitch_threshold and
            abs(roll_deg) < self.roll_threshold
        )
        
        return HeadPoseResult(
            yaw=yaw_deg,
            pitch=pitch_deg,
            roll=roll_deg,
            rotation_matrix=rotation_matrix,
            translation_vector=translation_vector.flatten(),
            head_movement_valid=head_movement_valid,
            movement_threshold=(self.yaw_threshold, self.pitch_threshold, self.roll_threshold)
        )
    
    def detect_spoof(
        self,
        landmarks: np.ndarray,
        image: np.ndarray
    ) -> SpoofDetectionResult:
        """
        Detect spoof attacks using texture and depth analysis.
        
        Args:
            landmarks: All facial landmarks
            image: Original image
            
        Returns:
            SpoofDetectionResult with spoof confidence
        """
        spoof_indicators = []
        
        # 1. Texture variance analysis
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Extract face region
        if landmarks is not None and len(landmarks) > 0:
            x_coords = landmarks[:, 0]
            y_coords = landmarks[:, 1]
            
            x_min, x_max = int(np.min(x_coords)), int(np.max(x_coords))
            y_min, y_max = int(np.min(y_coords)), int(np.max(y_coords))
            
            # Ensure bounds are within image
            height, width = image.shape[:2]
            x_min = max(0, x_min)
            x_max = min(width, x_max)
            y_min = max(0, y_min)
            y_max = min(height, y_max)
            
            if x_max > x_min and y_max > y_min:
                face_region = gray_image[y_min:y_max, x_min:x_max]
                texture_variance = np.var(face_region)
            else:
                texture_variance = 0.0
        else:
            texture_variance = 0.0
        
        # 2. Depth variance analysis (using z-coordinates from landmarks)
        if landmarks is not None and landmarks.shape[1] >= 3:
            depth_values = landmarks[:, 2]
            depth_variance = np.var(depth_values)
        else:
            depth_variance = 0.0
        
        # 3. Motion score (placeholder - would need temporal data)
        motion_score = 0.0
        
        # 4. Analyze spoof indicators
        if texture_variance < self.TEXTURE_VARIANCE_THRESHOLD:
            spoof_indicators.append("Low texture variance (possible photo)")
        
        if depth_variance < self.DEPTH_VARIANCE_THRESHOLD:
            spoof_indicators.append("Low depth variance (possible flat surface)")
        
        # Calculate spoof confidence
        spoof_score = 0.0
        if texture_variance < self.TEXTURE_VARIANCE_THRESHOLD:
            spoof_score += 0.4
        if depth_variance < self.DEPTH_VARIANCE_THRESHOLD:
            spoof_score += 0.4
        if motion_score < self.MOTION_THRESHOLD:
            spoof_score += 0.2
        
        spoof_confidence = min(spoof_score, 1.0)
        is_spoof = spoof_confidence > self.spoof_threshold
        
        return SpoofDetectionResult(
            texture_variance=texture_variance,
            depth_variance=depth_variance,
            motion_score=motion_score,
            spoof_confidence=spoof_confidence,
            is_spoof=is_spoof,
            spoof_indicators=spoof_indicators
        )
    
    def verify_driver_liveness(
        self,
        frame_bytes_or_landmarks: Union[bytes, np.ndarray, LandmarkExtractionResult],
        original_image: Optional[np.ndarray] = None
    ) -> LivenessVerificationResult:
        """
        Perform comprehensive liveness verification.
        
        Args:
            frame_bytes_or_landmarks: Image frame (bytes/numpy) or pre-extracted landmarks
            original_image: Original image for spoof detection (if landmarks provided)
            
        Returns:
            LivenessVerificationResult with comprehensive liveness assessment
        """
        try:
            # Extract landmarks if image provided
            if isinstance(frame_bytes_or_landmarks, (bytes, np.ndarray)):
                landmark_result = self.face_landmarker.extract_landmarks(frame_bytes_or_landmarks)
                original_image = self.face_landmarker._decode_image(frame_bytes_or_landmarks)
            elif isinstance(frame_bytes_or_landmarks, LandmarkExtractionResult):
                landmark_result = frame_bytes_or_landmarks
            else:
                return LivenessVerificationResult(
                    is_live=False,
                    blink_detected=False,
                    head_movement_valid=False,
                    spoof_confidence=1.0,
                    low_light_flag=False,
                    confidence_score=0.0,
                    status=LivenessStatus.ERROR,
                    eye_blink_result=None,
                    head_pose_result=None,
                    spoof_result=None,
                    error_message="Invalid input type"
                )
            
            # Check landmark extraction status
            if not landmark_result.is_successful():
                return LivenessVerificationResult(
                    is_live=False,
                    blink_detected=False,
                    head_movement_valid=False,
                    spoof_confidence=1.0,
                    low_light_flag=False,
                    confidence_score=0.0,
                    status=LivenessStatus.INSUFFICIENT_DATA,
                    eye_blink_result=None,
                    head_pose_result=None,
                    spoof_result=None,
                    error_message=landmark_result.error_message
                )
            
            # Detect eye blink
            eye_blink_result = self.detect_eye_blink(landmark_result.eye_landmarks)
            
            # Estimate head pose
            if original_image is not None:
                image_shape = original_image.shape[:2]
            else:
                # Default image shape
                image_shape = (480, 640)
            
            head_pose_result = self.estimate_head_pose(
                landmark_result.head_pose_landmarks,
                image_shape
            )
            
            # Detect spoof
            spoof_result = self.detect_spoof(
                landmark_result.all_landmarks,
                original_image
            )
            
            # Calculate overall confidence score
            confidence_score = landmark_result.confidence
            
            # Determine liveness status
            is_live = (
                not spoof_result.is_spoof and
                head_pose_result.head_movement_valid and
                confidence_score > 0.5
            )
            
            # Check for low light (will be handled by low_light_fallback)
            low_light_flag = False
            if original_image is not None:
                gray_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
                mean_brightness = np.mean(gray_image)
                low_light_flag = mean_brightness < 40  # Threshold from spec
            
            # Determine overall status
            if spoof_result.is_spoof:
                status = LivenessStatus.SPOOF_DETECTED
            elif is_live:
                status = LivenessStatus.LIVE
            else:
                status = LivenessStatus.INSUFFICIENT_DATA
            
            # Build details dictionary
            details = {
                'landmark_confidence': landmark_result.confidence,
                'face_area': landmark_result.bounding_box.area() if landmark_result.bounding_box else 0.0,
                'ear_values': {
                    'left': eye_blink_result.left_ear,
                    'right': eye_blink_result.right_ear,
                    'average': eye_blink_result.average_ear
                },
                'head_pose': {
                    'yaw': head_pose_result.yaw,
                    'pitch': head_pose_result.pitch,
                    'roll': head_pose_result.roll
                }
            }
            
            return LivenessVerificationResult(
                is_live=is_live,
                blink_detected=eye_blink_result.blink_detected,
                head_movement_valid=head_pose_result.head_movement_valid,
                spoof_confidence=spoof_result.spoof_confidence,
                low_light_flag=low_light_flag,
                confidence_score=confidence_score,
                status=status,
                eye_blink_result=eye_blink_result,
                head_pose_result=head_pose_result,
                spoof_result=spoof_result,
                details=details
            )
            
        except Exception as e:
            logger.error(f"Liveness verification error: {str(e)}")
            return LivenessVerificationResult(
                is_live=False,
                blink_detected=False,
                head_movement_valid=False,
                spoof_confidence=1.0,
                low_light_flag=False,
                confidence_score=0.0,
                status=LivenessStatus.ERROR,
                eye_blink_result=None,
                head_pose_result=None,
                spoof_result=None,
                error_message=str(e)
            )
    
    def verify_liveness_sequence(
        self,
        frame_sequence: List[Union[bytes, np.ndarray]],
        min_blinks: int = 1,
        min_head_movements: int = 1
    ) -> LivenessVerificationResult:
        """
        Verify liveness from a sequence of frames.
        
        Args:
            frame_sequence: List of frames to analyze
            min_blinks: Minimum number of blinks required
            min_head_movements: Minimum number of head movements required
            
        Returns:
            Aggregated LivenessVerificationResult
        """
        if not frame_sequence:
            return LivenessVerificationResult(
                is_live=False,
                blink_detected=False,
                head_movement_valid=False,
                spoof_confidence=1.0,
                low_light_flag=False,
                confidence_score=0.0,
                status=LivenessStatus.INSUFFICIENT_DATA,
                eye_blink_result=None,
                head_pose_result=None,
                spoof_result=None,
                error_message="Empty frame sequence"
            )
        
        total_frames = len(frame_sequence)
        blink_count = 0
        head_movement_count = 0
        spoof_count = 0
        total_confidence = 0.0
        low_light_count = 0
        
        results = []
        for frame in frame_sequence:
            result = self.verify_driver_liveness(frame)
            results.append(result)
            
            if result.blink_detected:
                blink_count += 1
            if result.head_movement_valid:
                head_movement_count += 1
            if result.spoof_result and result.spoof_result.is_spoof:
                spoof_count += 1
            total_confidence += result.confidence_score
            if result.low_light_flag:
                low_light_count += 1
        
        # Calculate aggregated metrics
        avg_confidence = total_confidence / total_frames
        blink_detected = blink_count >= min_blinks
        head_movement_valid = head_movement_count >= min_head_movements
        spoof_confidence = spoof_count / total_frames
        low_light_flag = low_light_count > (total_frames / 2)
        
        # Determine overall liveness
        is_live = (
            blink_detected and
            head_movement_valid and
            spoof_confidence < self.spoof_threshold and
            avg_confidence > 0.5
        )
        
        # Determine status
        if spoof_confidence > self.spoof_threshold:
            status = LivenessStatus.SPOOF_DETECTED
        elif is_live:
            status = LivenessStatus.LIVE
        else:
            status = LivenessStatus.INSUFFICIENT_DATA
        
        # Return aggregated result
        return LivenessVerificationResult(
            is_live=is_live,
            blink_detected=blink_detected,
            head_movement_valid=head_movement_valid,
            spoof_confidence=spoof_confidence,
            low_light_flag=low_light_flag,
            confidence_score=avg_confidence,
            status=status,
            eye_blink_result=results[0].eye_blink_result if results else None,
            head_pose_result=results[0].head_pose_result if results else None,
            spoof_result=results[0].spoof_result if results else None,
            details={
                'total_frames': total_frames,
                'blink_count': blink_count,
                'head_movement_count': head_movement_count,
                'spoof_count': spoof_count,
                'low_light_count': low_light_count
            }
        )


def create_liveness_detector() -> PassiveLivenessDetector:
    """
    Factory function to create a configured PassiveLivenessDetector instance.
    
    Returns:
        Configured PassiveLivenessDetector instance
    """
    return PassiveLivenessDetector(
        ear_threshold=0.21,
        head_pose_thresholds=(30.0, 25.0, 20.0),
        spoof_threshold=0.5
    )


if __name__ == "__main__":
    # Test the passive liveness detector
    print("Testing PassiveLivenessDetector...")
    
    detector = create_liveness_detector()
    
    # Create a dummy image for testing
    dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Test liveness verification
    result = detector.verify_driver_liveness(dummy_image)
    
    print(f"Status: {result.status}")
    print(f"Is Live: {result.is_live}")
    print(f"Blink Detected: {result.blink_detected}")
    print(f"Head Movement Valid: {result.head_movement_valid}")
    print(f"Spoof Confidence: {result.spoof_confidence}")
    print(f"Low Light Flag: {result.low_light_flag}")
    print(f"Error message: {result.error_message}")
    
    print("\nPassiveLivenessDetector test completed!")
