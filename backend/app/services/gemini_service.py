"""
Gemini AI Incident Triage & Multimodal Safety Copilot Service

This module implements:
- Multimodal (text/audio/image) emergency incident parsing using Google Gemini
- Structured JSON incident classification (severity, category, recommended action)
- Real-time Safety Copilot chat assistant for in-ride safety questions
- Graceful degradation when Gemini API key is not configured

Author: OptimalRide AI Team
Date: 2026-09-27
"""

import base64
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai package not installed; Gemini features disabled")


INCIDENT_TRIAGE_SYSTEM_PROMPT = """You are an emergency incident triage assistant for a ride-hailing
safety platform. You receive a passenger or driver's description of an incident (text, and
optionally an audio transcript or image description) during or after a ride.

Analyze the input and respond ONLY with a JSON object with this exact schema:
{
  "severity": "low" | "medium" | "high" | "critical",
  "category": "harassment" | "accident" | "route_deviation" | "vehicle_issue" | "medical" | "assault" | "other",
  "summary": "<one sentence summary>",
  "recommended_action": "<short actionable recommendation for the safety team>",
  "requires_police_dispatch": true | false,
  "requires_immediate_callback": true | false,
  "confidence": <float between 0 and 1>
}
Do not include any text outside the JSON object.
"""

SAFETY_COPILOT_SYSTEM_PROMPT = """You are "Guardian Copilot", a calm, concise in-ride safety
assistant embedded in a ride-hailing app. Passengers may ask you things like "is my route safe",
"what do I do if the driver goes off route", or "call for help". Keep responses under 80 words,
be reassuring but action-oriented, and always mention the in-app SOS button when the situation
sounds urgent.
"""


class GeminiIncidentTriageResult:
    """Structured result of an incident triage analysis."""

    def __init__(
        self,
        severity: str,
        category: str,
        summary: str,
        recommended_action: str,
        requires_police_dispatch: bool,
        requires_immediate_callback: bool,
        confidence: float,
        raw_response: Optional[str] = None
    ):
        self.severity = severity
        self.category = category
        self.summary = summary
        self.recommended_action = recommended_action
        self.requires_police_dispatch = requires_police_dispatch
        self.requires_immediate_callback = requires_immediate_callback
        self.confidence = confidence
        self.raw_response = raw_response
        self.analyzed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "summary": self.summary,
            "recommended_action": self.recommended_action,
            "requires_police_dispatch": self.requires_police_dispatch,
            "requires_immediate_callback": self.requires_immediate_callback,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at.isoformat()
        }


class GeminiSafetyService:
    """
    Wraps Google Gemini for:
    1. Multimodal emergency incident triage (text + audio transcript + image).
    2. Conversational safety copilot for in-ride Q&A.

    Falls back to a deterministic heuristic classifier when the Gemini API
    key is not configured or the SDK call fails, so the platform remains
    functional in offline/dev environments.
    """

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model_name
        self.vision_model_name = settings.gemini_vision_model_name
        self.timeout = settings.gemini_timeout_seconds
        self.max_retries = settings.gemini_max_retries
        self._configured = False

        if GENAI_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self._configured = True
                logger.info("Gemini Safety Service configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure Gemini: {e}")
        else:
            logger.warning(
                "Gemini Safety Service running in FALLBACK mode "
                "(no API key or SDK unavailable)"
            )

    @property
    def is_live(self) -> bool:
        """Whether real Gemini calls will be made (vs heuristic fallback)."""
        return self._configured

    async def triage_incident(
        self,
        text_description: Optional[str] = None,
        audio_transcript: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: str = "image/jpeg",
        ride_context: Optional[Dict[str, Any]] = None
    ) -> GeminiIncidentTriageResult:
        """
        Perform multimodal incident triage.

        Args:
            text_description: Raw text incident description from user
            audio_transcript: Transcribed audio report (if voice note supplied)
            image_base64: Base64-encoded incident photo (optional)
            image_mime_type: MIME type of the supplied image
            ride_context: Optional dict with ride_id, vehicle_type, route info etc.

        Returns:
            GeminiIncidentTriageResult with structured severity/category/action
        """
        combined_text = self._build_combined_prompt(
            text_description, audio_transcript, ride_context
        )

        if not self._configured:
            return self._heuristic_triage(combined_text)

        for attempt in range(self.max_retries + 1):
            try:
                model = genai.GenerativeModel(
                    self.vision_model_name if image_base64 else self.model_name,
                    system_instruction=INCIDENT_TRIAGE_SYSTEM_PROMPT
                )

                parts: List[Any] = [combined_text]
                if image_base64:
                    parts.append({
                        "mime_type": image_mime_type,
                        "data": base64.b64decode(image_base64)
                    })

                response = model.generate_content(
                    parts,
                    generation_config={
                        "temperature": 0.2,
                        "response_mime_type": "application/json"
                    }
                )

                parsed = json.loads(response.text)
                return GeminiIncidentTriageResult(
                    severity=parsed.get("severity", "medium"),
                    category=parsed.get("category", "other"),
                    summary=parsed.get("summary", combined_text[:200]),
                    recommended_action=parsed.get(
                        "recommended_action", "Escalate to safety team for review"
                    ),
                    requires_police_dispatch=bool(parsed.get("requires_police_dispatch", False)),
                    requires_immediate_callback=bool(
                        parsed.get("requires_immediate_callback", False)
                    ),
                    confidence=float(parsed.get("confidence", 0.7)),
                    raw_response=response.text
                )

            except Exception as e:
                logger.error(f"Gemini triage attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries:
                    logger.error("All Gemini triage attempts failed, using heuristic fallback")
                    return self._heuristic_triage(combined_text)

        return self._heuristic_triage(combined_text)

    async def ask_safety_copilot(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        ride_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Ask the in-ride Safety Copilot a question and get a concise response.

        Args:
            user_message: The user's question/message
            conversation_history: List of {"role": "user"/"model", "text": "..."} turns
            ride_context: Optional ride metadata to ground the response

        Returns:
            The copilot's text response.
        """
        if not self._configured:
            return self._heuristic_copilot_response(user_message)

        try:
            model = genai.GenerativeModel(
                self.model_name,
                system_instruction=SAFETY_COPILOT_SYSTEM_PROMPT
            )

            history = []
            for turn in (conversation_history or []):
                history.append({
                    "role": turn.get("role", "user"),
                    "parts": [turn.get("text", "")]
                })

            chat = model.start_chat(history=history)

            context_prefix = ""
            if ride_context:
                context_prefix = f"[Ride context: {json.dumps(ride_context)}]\n"

            response = chat.send_message(
                context_prefix + user_message,
                generation_config={"temperature": 0.4}
            )
            return response.text.strip()

        except Exception as e:
            logger.error(f"Gemini safety copilot failed: {e}")
            return self._heuristic_copilot_response(user_message)

    @staticmethod
    def _build_combined_prompt(
        text_description: Optional[str],
        audio_transcript: Optional[str],
        ride_context: Optional[Dict[str, Any]]
    ) -> str:
        segments = []
        if ride_context:
            segments.append(f"Ride context: {json.dumps(ride_context)}")
        if text_description:
            segments.append(f"Text report: {text_description}")
        if audio_transcript:
            segments.append(f"Audio transcript: {audio_transcript}")
        if not segments:
            segments.append("No description provided; passenger triggered emergency button only.")
        return "\n".join(segments)

    @staticmethod
    def _heuristic_triage(combined_text: str) -> "GeminiIncidentTriageResult":
        """Deterministic keyword-based fallback classifier."""
        text_lower = combined_text.lower()

        critical_keywords = ["assault", "attack", "weapon", "kidnap", "unconscious", "gun", "knife"]
        high_keywords = ["accident", "crash", "collision", "harassment", "threat", "following me"]
        medium_keywords = ["off route", "detour", "uncomfortable", "rude", "speeding"]

        if any(k in text_lower for k in critical_keywords):
            severity, category, police, callback, conf = (
                "critical", "assault", True, True, 0.55
            )
        elif any(k in text_lower for k in high_keywords):
            severity, category, police, callback, conf = (
                "high",
                "accident" if ("accident" in text_lower or "crash" in text_lower) else "harassment",
                True, True, 0.5
            )
        elif any(k in text_lower for k in medium_keywords):
            severity, category, police, callback, conf = (
                "medium", "route_deviation", False, True, 0.45
            )
        else:
            severity, category, police, callback, conf = (
                "low", "other", False, False, 0.35
            )

        return GeminiIncidentTriageResult(
            severity=severity,
            category=category,
            summary=combined_text[:200],
            recommended_action=(
                "Dispatch emergency response and notify local authorities immediately"
                if police else
                "Route to safety team for manual review within 15 minutes"
            ),
            requires_police_dispatch=police,
            requires_immediate_callback=callback,
            confidence=conf,
            raw_response=None
        )

    @staticmethod
    def _heuristic_copilot_response(user_message: str) -> str:
        text_lower = user_message.lower()
        if any(k in text_lower for k in ["help", "danger", "scared", "unsafe", "emergency"]):
            return (
                "I hear you. If you feel unsafe right now, tap the red SOS button to alert "
                "emergency contacts and our safety team instantly with your live location."
            )
        if "route" in text_lower:
            return (
                "Your driver's route is being tracked live against the expected corridor. "
                "You'll be alerted automatically if there's an unexpected deviation."
            )
        return (
            "I'm here to help with any safety concerns during your ride. "
            "You can always use the SOS button for immediate assistance."
        )


# Global singleton instance
gemini_safety_service = GeminiSafetyService()

