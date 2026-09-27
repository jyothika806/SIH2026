"""
Gemini AI Incident Triage & Safety Copilot API Endpoints

This module implements:
- Multimodal incident triage endpoint (text/audio/image)
- Safety Copilot chat endpoint
- Incident classification and severity scoring

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal
from datetime import datetime

from app.api.v1.auth import get_current_user
from app.services.gemini_service import gemini_safety_service, GeminiIncidentTriageResult

router = APIRouter(prefix="/gemini", tags=["Gemini AI Safety"])


# Pydantic Schemas
class IncidentTriageRequest(BaseModel):
    """Incident triage request schema."""
    
    text_description: Optional[str] = Field(None, description="Text incident description")
    audio_transcript: Optional[str] = Field(None, description="Transcribed audio report")
    image_base64: Optional[str] = Field(None, description="Base64-encoded incident photo")
    image_mime_type: str = Field("image/jpeg", description="Image MIME type")
    ride_context: Optional[Dict] = Field(None, description="Ride context metadata")


class IncidentTriageResponse(BaseModel):
    """Incident triage response schema."""
    
    severity: str = Field(..., description="Incident severity level")
    category: str = Field(..., description="Incident category")
    summary: str = Field(..., description="Incident summary")
    recommended_action: str = Field(..., description="Recommended action")
    requires_police_dispatch: bool = Field(..., description="Whether police dispatch is needed")
    requires_immediate_callback: bool = Field(..., description="Whether immediate callback is needed")
    confidence: float = Field(..., description="Classification confidence")
    analyzed_at: str = Field(..., description="Analysis timestamp")
    is_gemini_live: bool = Field(..., description="Whether Gemini API was used")


class SafetyCopilotRequest(BaseModel):
    """Safety Copilot chat request schema."""
    
    user_message: str = Field(..., description="User's message to the copilot")
    conversation_history: Optional[List[Dict]] = Field(None, description="Conversation history")
    ride_context: Optional[Dict] = Field(None, description="Ride context metadata")


class SafetyCopilotResponse(BaseModel):
    """Safety Copilot chat response schema."""
    
    response: str = Field(..., description="Copilot's response")
    is_gemini_live: bool = Field(..., description="Whether Gemini API was used")


# API Endpoints
@router.post("/triage", response_model=IncidentTriageResponse)
async def triage_incident(
    request: IncidentTriageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Perform multimodal incident triage using Gemini AI.
    
    Analyzes text, audio transcript, and optional image to classify
    incident severity, category, and recommend actions.
    
    Args:
        request: Incident triage data
        current_user: Current user from JWT token
        
    Returns:
        IncidentTriageResponse with classification results
    """
    try:
        # Perform triage
        result: GeminiIncidentTriageResult = await gemini_safety_service.triage_incident(
            text_description=request.text_description,
            audio_transcript=request.audio_transcript,
            image_base64=request.image_base64,
            image_mime_type=request.image_mime_type,
            ride_context=request.ride_context
        )
        
        return IncidentTriageResponse(
            severity=result.severity,
            category=result.category,
            summary=result.summary,
            recommended_action=result.recommended_action,
            requires_police_dispatch=result.requires_police_dispatch,
            requires_immediate_callback=result.requires_immediate_callback,
            confidence=result.confidence,
            analyzed_at=result.analyzed_at.isoformat(),
            is_gemini_live=gemini_safety_service.is_live
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incident triage failed: {str(e)}"
        )


@router.post("/safety-copilot", response_model=SafetyCopilotResponse)
async def ask_safety_copilot(
    request: SafetyCopilotRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Ask the in-ride Safety Copilot a question.
    
    Provides conversational AI assistance for safety-related questions
    during rides.
    
    Args:
        request: Safety copilot chat data
        current_user: Current user from JWT token
        
    Returns:
        SafetyCopilotResponse with copilot's answer
    """
    try:
        # Get copilot response
        response = await gemini_safety_service.ask_safety_copilot(
            user_message=request.user_message,
            conversation_history=request.conversation_history,
            ride_context=request.ride_context
        )
        
        return SafetyCopilotResponse(
            response=response,
            is_gemini_live=gemini_safety_service.is_live
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety copilot request failed: {str(e)}"
        )


@router.get("/status")
async def get_gemini_status():
    """
    Get Gemini AI service status.
    
    Returns:
        Status information about the Gemini service
    """
    return {
        "is_live": gemini_safety_service.is_live,
        "model_name": gemini_safety_service.model_name,
        "vision_model_name": gemini_safety_service.vision_model_name,
        "timeout_seconds": gemini_safety_service.timeout,
        "max_retries": gemini_safety_service.max_retries
    }
