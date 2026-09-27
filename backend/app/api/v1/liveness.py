"""
FastAPI Liveness Detection Endpoints with State Machine

This module implements:
- State machine REST & WebSocket API for Pre-OTP verification workflow
- POST /api/v1/liveness/request-verification - Trigger verification request
- POST /api/v1/liveness/verify-driver-scan - Accept live driver frame
- POST /api/v1/liveness/biometric-fallback - Fallback authentication
- GET /api/v1/liveness/otp-status/{ride_id} - OTP status with state machine

Author: OptimalRide AI Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Literal, Dict
from datetime import datetime, timedelta
import sys
import os
import base64
import numpy as np
import json
import cv2
import uuid
import random
from enum import Enum

# Add ai_engine to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

try:
    from ai_engine.liveness_detection import (
        PassiveLivenessDetector,
        LivenessVerificationResult,
        LivenessStatus,
        LowLightFallbackHandler,
        FallbackResult,
        FallbackMethod
    )
except ImportError as e:
    # Fallback for development environment - try direct import
    try:
        # Add the liveness_detection directory to path
        liveness_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', '..', '..', 
            'ai_engine', 'liveness_detection'
        )
        if liveness_path not in sys.path:
            sys.path.append(liveness_path)
        
        from passive_liveness import (
            PassiveLivenessDetector,
            LivenessVerificationResult,
            LivenessStatus
        )
        from low_light_fallback import (
            LowLightFallbackHandler,
            FallbackResult,
            FallbackMethod
        )
    except ImportError as e2:
        raise ImportError(
            f"Failed to import liveness detection modules: {e}, {e2}. "
            f"Ensure ai_engine/liveness_detection is in the Python path."
        )

router = APIRouter(prefix="/liveness", tags=["Liveness Detection"])


# Enum for verification state
class VerificationState(Enum):
    """Verification state machine states."""
    PENDING = "pending"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    LOW_LIGHT_DETECTED = "low_light_detected"
    FALLBACK_REQUIRED = "fallback_required"
    Fallback_AUTHENTICATED = "fallback_authenticated"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"


# Enum for OTP status
class OTPStatus(Enum):
    """OTP release status."""
    LOCKED = "locked"
    READY = "ready"
    RELEASED = "released"
    EXPIRED = "expired"


# In-memory storage for verification sessions (in production, use Redis/database)
verification_sessions: Dict[str, Dict] = {}
otp_status_store: Dict[str, OTPStatus] = {}


# Pydantic Schemas
class VerificationRequest(BaseModel):
    """Request schema for initiating driver verification."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    ride_id: str = Field(..., description="Unique ride identifier")
    driver_id: str = Field(..., description="Driver identifier")
    passenger_id: str = Field(..., description="Passenger identifier")
    device_capabilities: Optional[Dict[str, bool]] = Field(
        default_factory=lambda: {
            'fingerprint': True,
            'faceid': True,
            'infrared': False
        },
        description="Device biometric capabilities"
    )
    infrared_available: bool = Field(False, description="Infrared sensor availability")
    verification_timeout_seconds: int = Field(
        300,
        ge=60,
        le=900,
        description="Verification timeout in seconds"
    )


class VerificationRequestResponse(BaseModel):
    """Response schema for verification request."""
    
    verification_id: str = Field(..., description="Unique verification session ID")
    state: str = Field(..., description="Current verification state")
    expires_at: datetime = Field(..., description="Verification session expiration")
    instructions: List[str] = Field(..., description="Verification instructions for driver")


class DriverScanRequest(BaseModel):
    """Request schema for driver liveness scan."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    verification_id: str = Field(..., description="Verification session ID")
    frame_data: str = Field(..., description="Base64 encoded image frame")
    frame_format: Literal['jpeg', 'png'] = Field('jpeg', description="Image format")
    sequence_number: Optional[int] = Field(None, ge=0, description="Frame sequence number")


class DriverScanResponse(BaseModel):
    """Response schema for driver scan result."""
    
    verification_id: str = Field(..., description="Verification session ID")
    state: str = Field(..., description="Updated verification state")
    is_live: bool = Field(..., description="Liveness verification result")
    blink_detected: bool = Field(..., description="Eye blink detected")
    head_movement_valid: bool = Field(..., description="Head movement valid")
    spoof_confidence: float = Field(..., description="Spoof detection confidence")
    low_light_flag: bool = Field(..., description="Low light condition detected")
    confidence_score: float = Field(..., description="Overall confidence score")
    fallback_required: bool = Field(..., description="Fallback authentication required")
    fallback_method: Optional[str] = Field(None, description="Fallback method if required")
    details: Optional[Dict] = Field(None, description="Additional verification details")


class BiometricFallbackRequest(BaseModel):
    """Request schema for biometric fallback authentication."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    verification_id: str = Field(..., description="Verification session ID")
    auth_token: str = Field(..., description="Authentication token from fallback payload")
    biometric_method: Literal['fingerprint', 'faceid', 'infrared'] = Field(
        ...,
        description="Biometric method used"
    )
    device_id: Optional[str] = Field(None, description="Device identifier for verification")


class BiometricFallbackResponse(BaseModel):
    """Response schema for biometric fallback result."""
    
    verification_id: str = Field(..., description="Verification session ID")
    state: str = Field(..., description="Updated verification state")
    fallback_authenticated: bool = Field(..., description="Fallback authentication successful")
    otp_ready: bool = Field(..., description="OTP ready for release")
    auth_message: str = Field(..., description="Authentication status message")


class OTPStatusResponse(BaseModel):
    """Response schema for OTP status check."""
    
    ride_id: str = Field(..., description="Ride identifier")
    otp_status: str = Field(..., description="Current OTP status")
    verification_status: str = Field(..., description="Driver verification status")
    otp_code: Optional[str] = Field(None, description="OTP code if released")
    otp_expires_at: Optional[datetime] = Field(None, description="OTP expiration time")


class HealthResponse(BaseModel):
    """Response schema for health check."""
    
    status: str = Field(..., description="Service status")
    detectors_loaded: bool = Field(..., description="Liveness detectors loaded")
    fallback_handler_loaded: bool = Field(..., description="Fallback handler loaded")


# Global detector instances
_liveness_detector: Optional[PassiveLivenessDetector] = None
_fallback_handler: Optional[LowLightFallbackHandler] = None


def get_liveness_detector() -> PassiveLivenessDetector:
    """Get or initialize the global liveness detector."""
    global _liveness_detector
    if _liveness_detector is None:
        _liveness_detector = PassiveLivenessDetector()
    return _liveness_detector


def get_fallback_handler() -> LowLightFallbackHandler:
    """Get or initialize the global fallback handler."""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = LowLightFallbackHandler()
    return _fallback_handler


def _decode_base64_image(base64_string: str) -> np.ndarray:
    """
    Decode base64 encoded image to numpy array.
    
    Args:
        base64_string: Base64 encoded image string
        
    Returns:
        Image as numpy array (BGR format)
    """
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # Decode base64
    image_bytes = base64.b64decode(base64_string)
    
    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Failed to decode image from base64")
    
    return image


def _generate_verification_id() -> str:
    """Generate a unique verification ID."""
    return str(uuid.uuid4())


def _generate_otp_code() -> str:
    """Generate a 6-digit OTP code."""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def _update_session_state(
    verification_id: str,
    new_state: VerificationState,
    additional_data: Optional[Dict] = None
):
    """Update verification session state."""
    if verification_id not in verification_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found"
        )
    
    session = verification_sessions[verification_id]
    session['state'] = new_state.value
    session['updated_at'] = datetime.now()
    
    if additional_data:
        session.update(additional_data)
    
    # Check for expiration
    if session['expires_at'] < datetime.now():
        session['state'] = VerificationState.EXPIRED.value
        otp_status_store[session['ride_id']] = OTPStatus.EXPIRED


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for liveness detection service.
    
    Returns:
        HealthResponse with service status
    """
    try:
        _ = get_liveness_detector()
        _ = get_fallback_handler()
        return HealthResponse(
            status="healthy",
            detectors_loaded=True,
            fallback_handler_loaded=True
        )
    except Exception:
        return HealthResponse(
            status="unhealthy",
            detectors_loaded=False,
            fallback_handler_loaded=False
        )


@router.post(
    "/request-verification",
    response_model=VerificationRequestResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Verification request created successfully"},
        400: {"description": "Invalid request data"},
        409: {"description": "Verification already in progress for this ride"}
    }
)
async def request_verification(request: VerificationRequest) -> VerificationRequestResponse:
    """
    Request driver liveness verification.
    
    Triggered by passenger mobile app when driver arrives.
    Creates a verification session and locks OTP until verification succeeds.
    
    Returns:
        VerificationRequestResponse with session details
    """
    try:
        # Check if verification already exists for this ride
        existing_session = [
            session for session in verification_sessions.values()
            if session['ride_id'] == request.ride_id
            and session['state'] not in [
                VerificationState.SUCCESS.value,
                VerificationState.FAILED.value,
                VerificationState.EXPIRED.value
            ]
        ]
        
        if existing_session:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Verification already in progress for this ride"
            )
        
        # Generate verification ID
        verification_id = _generate_verification_id()
        
        # Calculate expiration
        expires_at = datetime.now() + timedelta(
            seconds=request.verification_timeout_seconds
        )
        
        # Create verification session
        verification_sessions[verification_id] = {
            'verification_id': verification_id,
            'ride_id': request.ride_id,
            'driver_id': request.driver_id,
            'passenger_id': request.passenger_id,
            'device_capabilities': request.device_capabilities,
            'infrared_available': request.infrared_available,
            'state': VerificationState.REQUESTED.value,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'expires_at': expires_at,
            'scan_count': 0,
            'max_scans': 10  # Maximum scan attempts
        }
        
        # Lock OTP for this ride
        otp_status_store[request.ride_id] = OTPStatus.LOCKED
        
        # Generate instructions
        instructions = [
            "Position your face clearly in the camera frame",
            "Ensure adequate lighting - avoid very dark or backlit conditions",
            "Blink naturally when prompted",
            "Turn your head slightly left and right when prompted",
            "Keep your face within the frame throughout verification",
            "Verification will complete automatically when conditions are met"
        ]
        
        return VerificationRequestResponse(
            verification_id=verification_id,
            state=VerificationState.REQUESTED.value,
            expires_at=expires_at,
            instructions=instructions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create verification request: {str(e)}"
        )


@router.post(
    "/verify-driver-scan",
    response_model=DriverScanResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Driver scan processed successfully"},
        400: {"description": "Invalid request data or image"},
        404: {"description": "Verification session not found"},
        410: {"description": "Verification session expired"}
    }
)
async def verify_driver_scan(request: DriverScanRequest) -> DriverScanResponse:
    """
    Process driver liveness scan.
    
    Accepts live driver frame/video stream and runs passive liveness detection.
    Handles low-light conditions and triggers fallback if needed.
    
    Returns:
        DriverScanResponse with verification results
    """
    try:
        # Check verification session
        if request.verification_id not in verification_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification session not found"
            )
        
        session = verification_sessions[request.verification_id]
        
        # Check expiration
        if session['expires_at'] < datetime.now():
            _update_session_state(request.verification_id, VerificationState.EXPIRED)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Verification session has expired"
            )
        
        # Update session state
        _update_session_state(request.verification_id, VerificationState.IN_PROGRESS)
        
        # Increment scan count
        session['scan_count'] += 1
        
        # Check max scans
        if session['scan_count'] > session['max_scans']:
            _update_session_state(request.verification_id, VerificationState.FAILED)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum scan attempts exceeded"
            )
        
        # Decode image
        try:
            image = _decode_base64_image(request.frame_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decode image: {str(e)}"
            )
        
        # Get liveness detector
        detector = get_liveness_detector()
        
        # Perform liveness verification
        liveness_result = detector.verify_driver_liveness(image)
        
        # Handle low-light condition
        fallback_required = False
        fallback_method = None
        
        if liveness_result.low_light_flag:
            # Get fallback handler
            fallback_handler = get_fallback_handler()
            
            # Process low-light frame
            light_assessment, enhancement_result, fallback_result = (
                fallback_handler.process_low_light_frame(
                    image,
                    device_capabilities=session['device_capabilities'],
                    infrared_available=session['infrared_available']
                )
            )
            
            # Update session state if fallback triggered
            if fallback_result and fallback_result.fallback_triggered:
                _update_session_state(
                    request.verification_id,
                    VerificationState.FALLBACK_REQUIRED,
                    {
                        'fallback_payload': fallback_handler.auth_payload_to_dict(
                            fallback_result.auth_payload
                        ) if fallback_result.auth_payload else None
                    }
                )
                fallback_required = True
                fallback_method = fallback_result.fallback_method.value if fallback_result.fallback_method else None
        
        # Determine final state
        if liveness_result.is_live and not fallback_required:
            # Verification successful
            _update_session_state(
                request.verification_id,
                VerificationState.SUCCESS
            )
            otp_status_store[session['ride_id']] = OTPStatus.READY
        elif fallback_required:
            # Fallback required
            _update_session_state(
                request.verification_id,
                VerificationState.FALLBACK_REQUIRED
            )
        else:
            # Verification failed, stay in progress
            _update_session_state(
                request.verification_id,
                VerificationState.IN_PROGRESS
            )
        
        # Build response
        response = DriverScanResponse(
            verification_id=request.verification_id,
            state=verification_sessions[request.verification_id]['state'],
            is_live=liveness_result.is_live,
            blink_detected=liveness_result.blink_detected,
            head_movement_valid=liveness_result.head_movement_valid,
            spoof_confidence=liveness_result.spoof_confidence,
            low_light_flag=liveness_result.low_light_flag,
            confidence_score=liveness_result.confidence_score,
            fallback_required=fallback_required,
            fallback_method=fallback_method,
            details=liveness_result.details if liveness_result.details else {}
        )
        
        return JSONResponse(
            content=response.model_dump(),
            headers={
                "X-Verification-State": verification_sessions[request.verification_id]['state'],
                "X-Scan-Count": str(session['scan_count'])
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Driver scan verification failed: {str(e)}"
        )


@router.post(
    "/biometric-fallback",
    response_model=BiometricFallbackResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Fallback authentication processed successfully"},
        400: {"description": "Invalid request or authentication failed"},
        404: {"description": "Verification session not found"}
    }
)
async def biometric_fallback(request: BiometricFallbackRequest) -> BiometricFallbackResponse:
    """
    Process biometric fallback authentication.
    
    Endpoint for fallback authentication when low-light conditions
    prevent standard liveness verification.
    
    Returns:
        BiometricFallbackResponse with authentication result
    """
    try:
        # Check verification session
        if request.verification_id not in verification_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification session not found"
            )
        
        session = verification_sessions[request.verification_id]
        
        # Check if fallback is available
        if session['state'] != VerificationState.FALLBACK_REQUIRED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fallback authentication not required for this session"
            )
        
        # Check expiration
        if session['expires_at'] < datetime.now():
            _update_session_state(request.verification_id, VerificationState.EXPIRED)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Verification session has expired"
            )
        
        # Verify auth token
        fallback_payload = session.get('fallback_payload')
        if not fallback_payload or fallback_payload.get('auth_token') != request.auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Check token expiration
        token_expires_at = datetime.fromisoformat(fallback_payload['expires_at'])
        if token_expires_at < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired"
            )
        
        # In a real implementation, verify the biometric data here
        # For now, we'll accept it as valid if the token is correct
        fallback_authenticated = True
        
        # Update session state
        if fallback_authenticated:
            _update_session_state(
                request.verification_id,
                VerificationState.Fallback_AUTHENTICATED
            )
            otp_status_store[session['ride_id']] = OTPStatus.READY
            auth_message = "Fallback authentication successful"
        else:
            _update_session_state(
                request.verification_id,
                VerificationState.FAILED
            )
            auth_message = "Fallback authentication failed"
        
        return BiometricFallbackResponse(
            verification_id=request.verification_id,
            state=verification_sessions[request.verification_id]['state'],
            fallback_authenticated=fallback_authenticated,
            otp_ready=fallback_authenticated,
            auth_message=auth_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Biometric fallback authentication failed: {str(e)}"
        )


@router.get(
    "/otp-status/{ride_id}",
    response_model=OTPStatusResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "OTP status retrieved successfully"},
        404: {"description": "Ride not found"}
    }
)
async def get_otp_status(ride_id: str) -> OTPStatusResponse:
    """
    Check OTP status for a ride.
    
    Returns OTP status and releases OTP code only when driver verification
    status is SUCCESS. OTP remains locked until verification succeeds.
    
    Args:
        ride_id: Ride identifier
        
    Returns:
        OTPStatusResponse with current OTP status
    """
    try:
        # Get OTP status
        otp_status = otp_status_store.get(ride_id, OTPStatus.LOCKED)
        
        # Find verification session for this ride
        verification_session = None
        for session in verification_sessions.values():
            if session['ride_id'] == ride_id:
                verification_session = session
                break
        
        if not verification_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No verification session found for this ride"
            )
        
        verification_status = verification_session['state']
        
        # Generate OTP if ready and not yet released
        otp_code = None
        otp_expires_at = None
        
        if otp_status == OTPStatus.READY and verification_status == VerificationState.SUCCESS.value:
            otp_code = _generate_otp_code()
            otp_expires_at = datetime.now() + timedelta(minutes=5)  # OTP valid for 5 minutes
            otp_status_store[ride_id] = OTPStatus.RELEASED
        
        return OTPStatusResponse(
            ride_id=ride_id,
            otp_status=otp_status.value,
            verification_status=verification_status,
            otp_code=otp_code,
            otp_expires_at=otp_expires_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve OTP status: {str(e)}"
        )


@router.websocket("/ws/verification/{verification_id}")
async def websocket_verification(websocket: WebSocket, verification_id: str):
    """
    WebSocket endpoint for real-time verification updates.
    
    Provides real-time updates on verification status for mobile clients.
    
    Args:
        websocket: WebSocket connection
        verification_id: Verification session ID
    """
    await websocket.accept()
    
    try:
        # Check if verification session exists
        if verification_id not in verification_sessions:
            await websocket.send_json({
                "error": "Verification session not found"
            })
            await websocket.close()
            return
        
        session = verification_sessions[verification_id]
        
        # Send initial state
        await websocket.send_json({
            "type": "state_update",
            "verification_id": verification_id,
            "state": session['state'],
            "ride_id": session['ride_id'],
            "scan_count": session['scan_count']
        })
        
        # Keep connection alive and send updates
        # In production, use a proper event system
        while True:
            # Wait for client messages
            data = await websocket.receive_json()
            
            if data.get('type') == 'ping':
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            elif data.get('type') == 'get_state':
                session = verification_sessions.get(verification_id)
                if session:
                    await websocket.send_json({
                        "type": "state_update",
                        "verification_id": verification_id,
                        "state": session['state'],
                        "ride_id": session['ride_id'],
                        "scan_count": session['scan_count']
                    })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for verification {verification_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.close()


@router.delete("/sessions/{verification_id}")
async def cancel_verification(verification_id: str):
    """
    Cancel an ongoing verification session.
    
    Args:
        verification_id: Verification session ID to cancel
    """
    try:
        if verification_id not in verification_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification session not found"
            )
        
        session = verification_sessions[verification_id]
        
        # Update state to failed
        _update_session_state(verification_id, VerificationState.FAILED)
        
        # Update OTP status
        otp_status_store[session['ride_id']] = OTPStatus.LOCKED
        
        return {
            "message": "Verification session cancelled",
            "verification_id": verification_id,
            "state": VerificationState.FAILED.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel verification: {str(e)}"
        )
