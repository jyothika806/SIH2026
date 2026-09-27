"""
MediaPipe 3D Face Landmark Extractor & Mesh Processing

This module implements:
- MediaPipe Face Mesh for 3D facial landmark extraction
- Key landmark extraction for eye blink detection (EAR calculation)
- Head pose estimation landmarks (nose, chin, eye corners, mouth corners)
- Face bounding box and spatial metrics
- Robust error handling for missing faces and poor lighting

Author: OptimalRide AI Team
Date: 2026-09-27
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Optional, Tuple, Dict, List, Union
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LandmarkExtractionError(Exception):
    """Custom exception for landmark extraction failures."""
    pass


class DetectionStatus(Enum):
    """Status of face detection."""
    SUCCESS = "success"
    NO_FACE_DETECTED = "no_face_detected"
    MULTIPLE_FACES_DETECTED = "multiple_faces_detected"
    LOW_CONFIDENCE = "low_confidence"
    PROCESSING_ERROR = "processing_error"


@dataclass
class EyeLandmarks:
    """Eye landmarks for EAR calculation."""
    left_eye: List[Tuple[float, float, float]]  # 6 points
    right_eye: List[Tuple[float, float, float]]  # 6 points
    
    def to_numpy(self) -> Dict[str, np.ndarray]:
        """Convert to numpy arrays for processing."""
        return {
            'left': np.array(self.left_eye),
            'right': np.array(self.right_eye)
        }


@dataclass
class HeadPoseLandmarks:
    """Landmarks for 3D head pose estimation."""
    nose_tip: Tuple[float, float, float]
    chin: Tuple[float, float, float]
    left_eye_corner: Tuple[float, float, float]
    right_eye_corner: Tuple[float, float, float]
    left_mouth_corner: Tuple[float, float, float]
    right_mouth_corner: Tuple[float, float, float]
    
    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array for solvePnP."""
        return np.array([
            self.nose_tip,
            self.chin,
            self.left_eye_corner,
            self.right_eye_corner,
            self.left_mouth_corner,
            self.right_mouth_corner
        ], dtype=np.float64)


@dataclass
class FaceBoundingBox:
    """Face bounding box metrics."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    width: float
    height: float
    center_x: float
    center_y: float
    
    def area(self) -> float:
        """Calculate bounding box area."""
        return self.width * self.height
    
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height if self.height > 0 else 0.0


@dataclass
class LandmarkExtractionResult:
    """Complete result of landmark extraction."""
    status: DetectionStatus
    confidence: float
    eye_landmarks: Optional[EyeLandmarks]
    head_pose_landmarks: Optional[HeadPoseLandmarks]
    bounding_box: Optional[FaceBoundingBox]
    all_landmarks: Optional[np.ndarray]
    error_message: Optional[str] = None
    
    def is_successful(self) -> bool:
        """Check if extraction was successful."""
        return self.status == DetectionStatus.SUCCESS and self.confidence > 0.5


class FaceLandmarker:
    """
    MediaPipe 3D Face Landmark Extractor.
    
    Extracts 468 3D facial landmarks using MediaPipe Face Mesh,
    with specialized methods for key landmark extraction.
    """
    
    # MediaPipe Face Mesh landmark indices
    # Left eye landmarks (6 points for EAR calculation)
    LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
    
    # Head pose landmarks
    NOSE_TIP_INDEX = 1
    CHIN_INDEX = 152
    LEFT_EYE_CORNER_INDEX = 33
    RIGHT_EYE_CORNER_INDEX = 263
    LEFT_MOUTH_CORNER_INDEX = 61
    RIGHT_MOUTH_CORNER_INDEX = 291
    
    # 3D model points for head pose estimation (normalized coordinates)
    MODEL_POINTS = np.array([
        (0.0, 0.0, 0.0),             # Nose tip
        (0.0, -330.0, -65.0),        # Chin
        (-225.0, 170.0, -135.0),     # Left eye corner
        (225.0, 170.0, -135.0),      # Right eye corner
        (-150.0, -150.0, -125.0),    # Left mouth corner
        (150.0, -150.0, -125.0)      # Right mouth corner
    ])
    
    def __init__(
        self,
        max_num_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1
    ):
        """
        Initialize the Face Landmarker.
        
        Args:
            max_num_faces: Maximum number of faces to detect
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
            model_complexity: Model complexity (0 or 1)
        """
        self.max_num_faces = max_num_faces
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity
        
        # Initialize MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_num_faces,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=model_complexity
        )
        
        logger.info("FaceLandmarker initialized successfully")
    
    def _decode_image(
        self,
        image_input: Union[bytes, np.ndarray]
    ) -> np.ndarray:
        """
        Decode image from bytes or numpy array.
        
        Args:
            image_input: Image as bytes or numpy array
            
        Returns:
            Decoded image as numpy array (BGR format)
            
        Raises:
            LandmarkExtractionError: If image decoding fails
        """
        try:
            if isinstance(image_input, bytes):
                # Decode from bytes
                nparr = np.frombuffer(image_input, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if image is None:
                    raise LandmarkExtractionError("Failed to decode image from bytes")
            elif isinstance(image_input, np.ndarray):
                # Assume already decoded
                image = image_input
            else:
                raise LandmarkExtractionError(
                    f"Unsupported input type: {type(image_input)}"
                )
            
            # Validate image
            if image.size == 0:
                raise LandmarkExtractionError("Empty image provided")
            
            if len(image.shape) != 3 or image.shape[2] != 3:
                raise LandmarkExtractionError(
                    f"Invalid image shape: {image.shape}. Expected (H, W, 3)"
                )
            
            return image
            
        except Exception as e:
            raise LandmarkExtractionError(f"Image decoding failed: {str(e)}")
    
    def _extract_eye_landmarks(
        self,
        landmarks: List,
        image_shape: Tuple[int, int]
    ) -> EyeLandmarks:
        """
        Extract eye landmarks for EAR calculation.
        
        Args:
            landmarks: MediaPipe landmarks list
            image_shape: Image shape (height, width)
            
        Returns:
            EyeLandmarks object with left and right eye coordinates
        """
        height, width = image_shape
        
        # Extract left eye landmarks
        left_eye = []
        for idx in self.LEFT_EYE_INDICES:
            landmark = landmarks[idx]
            left_eye.append((
                landmark.x * width,
                landmark.y * height,
                landmark.z  # Depth coordinate
            ))
        
        # Extract right eye landmarks
        right_eye = []
        for idx in self.RIGHT_EYE_INDICES:
            landmark = landmarks[idx]
            right_eye.append((
                landmark.x * width,
                landmark.y * height,
                landmark.z  # Depth coordinate
            ))
        
        return EyeLandmarks(left_eye=left_eye, right_eye=right_eye)
    
    def _extract_head_pose_landmarks(
        self,
        landmarks: List,
        image_shape: Tuple[int, int]
    ) -> HeadPoseLandmarks:
        """
        Extract landmarks for 3D head pose estimation.
        
        Args:
            landmarks: MediaPipe landmarks list
            image_shape: Image shape (height, width)
            
        Returns:
            HeadPoseLandmarks object with pose-relevant landmarks
        """
        height, width = image_shape
        
        # Extract pose landmarks
        nose_tip = (
            landmarks[self.NOSE_TIP_INDEX].x * width,
            landmarks[self.NOSE_TIP_INDEX].y * height,
            landmarks[self.NOSE_TIP_INDEX].z
        )
        
        chin = (
            landmarks[self.CHIN_INDEX].x * width,
            landmarks[self.CHIN_INDEX].y * height,
            landmarks[self.CHIN_INDEX].z
        )
        
        left_eye_corner = (
            landmarks[self.LEFT_EYE_CORNER_INDEX].x * width,
            landmarks[self.LEFT_EYE_CORNER_INDEX].y * height,
            landmarks[self.LEFT_EYE_CORNER_INDEX].z
        )
        
        right_eye_corner = (
            landmarks[self.RIGHT_EYE_CORNER_INDEX].x * width,
            landmarks[self.RIGHT_EYE_CORNER_INDEX].y * height,
            landmarks[self.RIGHT_EYE_CORNER_INDEX].z
        )
        
        left_mouth_corner = (
            landmarks[self.LEFT_MOUTH_CORNER_INDEX].x * width,
            landmarks[self.LEFT_MOUTH_CORNER_INDEX].y * height,
            landmarks[self.LEFT_MOUTH_CORNER_INDEX].z
        )
        
        right_mouth_corner = (
            landmarks[self.RIGHT_MOUTH_CORNER_INDEX].x * width,
            landmarks[self.RIGHT_MOUTH_CORNER_INDEX].y * height,
            landmarks[self.RIGHT_MOUTH_CORNER_INDEX].z
        )
        
        return HeadPoseLandmarks(
            nose_tip=nose_tip,
            chin=chin,
            left_eye_corner=left_eye_corner,
            right_eye_corner=right_eye_corner,
            left_mouth_corner=left_mouth_corner,
            right_mouth_corner=right_mouth_corner
        )
    
    def _calculate_bounding_box(
        self,
        landmarks: List,
        image_shape: Tuple[int, int]
    ) -> FaceBoundingBox:
        """
        Calculate face bounding box from landmarks.
        
        Args:
            landmarks: MediaPipe landmarks list
            image_shape: Image shape (height, width)
            
        Returns:
            FaceBoundingBox object with spatial metrics
        """
        height, width = image_shape
        
        # Extract all landmark coordinates
        x_coords = [landmark.x * width for landmark in landmarks]
        y_coords = [landmark.y * height for landmark in landmarks]
        
        x_min = min(x_coords)
        x_max = max(x_coords)
        y_min = min(y_coords)
        y_max = max(y_coords)
        
        bbox_width = x_max - x_min
        bbox_height = y_max - y_min
        center_x = x_min + bbox_width / 2
        center_y = y_min + bbox_height / 2
        
        return FaceBoundingBox(
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
            width=bbox_width,
            height=bbox_height,
            center_x=center_x,
            center_y=center_y
        )
    
    def extract_landmarks(
        self,
        image_input: Union[bytes, np.ndarray]
    ) -> LandmarkExtractionResult:
        """
        Extract 3D facial landmarks from image.
        
        Args:
            image_input: Image as bytes (JPEG/PNG) or numpy array (BGR)
            
        Returns:
            LandmarkExtractionResult with extracted landmarks and metadata
        """
        try:
            # Decode image
            image = self._decode_image(image_input)
            height, width = image.shape[:2]
            
            # Convert to RGB for MediaPipe
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Process with MediaPipe Face Mesh
            results = self.face_mesh.process(image_rgb)
            
            # Check if face detected
            if results.multi_face_landmarks is None:
                return LandmarkExtractionResult(
                    status=DetectionStatus.NO_FACE_DETECTED,
                    confidence=0.0,
                    eye_landmarks=None,
                    head_pose_landmarks=None,
                    bounding_box=None,
                    all_landmarks=None,
                    error_message="No face detected in image"
                )
            
            # Check for multiple faces
            if len(results.multi_face_landmarks) > 1:
                logger.warning(f"Multiple faces detected: {len(results.multi_face_landmarks)}")
                return LandmarkExtractionResult(
                    status=DetectionStatus.MULTIPLE_FACES_DETECTED,
                    confidence=0.0,
                    eye_landmarks=None,
                    head_pose_landmarks=None,
                    bounding_box=None,
                    all_landmarks=None,
                    error_message="Multiple faces detected. Please ensure only one face is visible."
                )
            
            # Get single face landmarks
            face_landmarks = results.multi_face_landmarks[0]
            landmarks = face_landmarks.landmark
            
            # Convert to numpy array for all landmarks
            all_landmarks_np = np.array([
                [lm.x * width, lm.y * height, lm.z]
                for lm in landmarks
            ])
            
            # Extract specialized landmarks
            eye_landmarks = self._extract_eye_landmarks(landmarks, (height, width))
            head_pose_landmarks = self._extract_head_pose_landmarks(landmarks, (height, width))
            bounding_box = self._calculate_bounding_box(landmarks, (height, width))
            
            # Estimate confidence (based on landmark visibility)
            visibility_scores = [lm.visibility for lm in landmarks]
            confidence = np.mean(visibility_scores)
            
            # Check confidence threshold
            if confidence < self.min_detection_confidence:
                return LandmarkExtractionResult(
                    status=DetectionStatus.LOW_CONFIDENCE,
                    confidence=confidence,
                    eye_landmarks=eye_landmarks,
                    head_pose_landmarks=head_pose_landmarks,
                    bounding_box=bounding_box,
                    all_landmarks=all_landmarks_np,
                    error_message=f"Low detection confidence: {confidence:.2f}"
                )
            
            return LandmarkExtractionResult(
                status=DetectionStatus.SUCCESS,
                confidence=confidence,
                eye_landmarks=eye_landmarks,
                head_pose_landmarks=head_pose_landmarks,
                bounding_box=bounding_box,
                all_landmarks=all_landmarks_np
            )
            
        except LandmarkExtractionError as e:
            logger.error(f"Landmark extraction error: {str(e)}")
            return LandmarkExtractionResult(
                status=DetectionStatus.PROCESSING_ERROR,
                confidence=0.0,
                eye_landmarks=None,
                head_pose_landmarks=None,
                bounding_box=None,
                all_landmarks=None,
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error in landmark extraction: {str(e)}")
            return LandmarkExtractionResult(
                status=DetectionStatus.PROCESSING_ERROR,
                confidence=0.0,
                eye_landmarks=None,
                head_pose_landmarks=None,
                bounding_box=None,
                all_landmarks=None,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def extract_landmarks_batch(
        self,
        image_inputs: List[Union[bytes, np.ndarray]]
    ) -> List[LandmarkExtractionResult]:
        """
        Extract landmarks from multiple images (batch processing).
        
        Args:
            image_inputs: List of images as bytes or numpy arrays
            
        Returns:
            List of LandmarkExtractionResult objects
        """
        results = []
        for image_input in image_inputs:
            result = self.extract_landmarks(image_input)
            results.append(result)
        return results
    
    def visualize_landmarks(
        self,
        image: np.ndarray,
        result: LandmarkExtractionResult,
        show: bool = False
    ) -> np.ndarray:
        """
        Visualize extracted landmarks on image.
        
        Args:
            image: Original image (BGR)
            result: Landmark extraction result
            show: Whether to display the image
            
        Returns:
            Image with landmarks drawn
        """
        if not result.is_successful() or result.all_landmarks is None:
            return image
        
        vis_image = image.copy()
        
        # Draw all landmarks
        for landmark in result.all_landmarks:
            cv2.circle(
                vis_image,
                (int(landmark[0]), int(landmark[1])),
                1,
                (0, 255, 0),
                -1
            )
        
        # Draw eye landmarks
        if result.eye_landmarks:
            for eye in [result.eye_landmarks.left_eye, result.eye_landmarks.right_eye]:
                for point in eye:
                    cv2.circle(
                        vis_image,
                        (int(point[0]), int(point[1])),
                        3,
                        (255, 0, 0),
                        -1
                    )
        
        # Draw head pose landmarks
        if result.head_pose_landmarks:
            pose_points = [
                result.head_pose_landmarks.nose_tip,
                result.head_pose_landmarks.chin,
                result.head_pose_landmarks.left_eye_corner,
                result.head_pose_landmarks.right_eye_corner,
                result.head_pose_landmarks.left_mouth_corner,
                result.head_pose_landmarks.right_mouth_corner
            ]
            for point in pose_points:
                cv2.circle(
                    vis_image,
                    (int(point[0]), int(point[1])),
                    5,
                    (0, 0, 255),
                    -1
                )
        
        # Draw bounding box
        if result.bounding_box:
            bbox = result.bounding_box
            cv2.rectangle(
                vis_image,
                (int(bbox.x_min), int(bbox.y_min)),
                (int(bbox.x_max), int(bbox.y_max)),
                (255, 255, 0),
                2
            )
        
        # Add confidence text
        cv2.putText(
            vis_image,
            f"Confidence: {result.confidence:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        if show:
            cv2.imshow('Landmarks', vis_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        
        return vis_image
    
    def __del__(self):
        """Cleanup MediaPipe resources."""
        if hasattr(self, 'face_mesh'):
            self.face_mesh.close()


def create_sample_landmarker() -> FaceLandmarker:
    """
    Factory function to create a configured FaceLandmarker instance.
    
    Returns:
        Configured FaceLandmarker instance
    """
    return FaceLandmarker(
        max_num_faces=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    )


if __name__ == "__main__":
    # Test the face landmarker
    print("Testing FaceLandmarker...")
    
    landmarker = create_sample_landmarker()
    
    # Create a dummy image for testing
    dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Test landmark extraction
    result = landmarker.extract_landmarks(dummy_image)
    
    print(f"Status: {result.status}")
    print(f"Confidence: {result.confidence}")
    print(f"Error message: {result.error_message}")
    
    print("\nFaceLandmarker test completed!")
