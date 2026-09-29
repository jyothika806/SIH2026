"""
Application Configuration using Pydantic BaseSettings

This module loads environment variables for:
- Database connection (PostgreSQL + PostGIS)
- JWT authentication settings
- Firebase Cloud Messaging (FCM) credentials
- Twilio SMS gateway keys
- OSRM route server endpoint
- Application settings

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional
import os
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables or .env file.
    """
    
    # Application Settings
    app_name: str = "OptimalRide API"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database Settings
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:JyothikA@localhost:5432/optimalride",
        description="PostgreSQL database URL with asyncpg driver"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600
    
    # JWT Settings
    jwt_secret_key: str = Field(
        ...,
        description="Secret key for JWT token signing"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # Firebase Cloud Messaging (FCM) Settings
    fcm_service_account_key_path: Optional[str] = Field(
        None,
        description="Path to Firebase service account JSON key"
    )
    fcm_api_key: Optional[str] = Field(
        None,
        description="Firebase Cloud Messaging API key"
    )
    fcm_project_id: Optional[str] = Field(
        None,
        description="Firebase project ID"
    )
    
    # Twilio SMS Settings
    twilio_account_sid: Optional[str] = Field(
        None,
        description="Twilio account SID"
    )
    twilio_auth_token: Optional[str] = Field(
        None,
        description="Twilio auth token"
    )
    twilio_phone_number: Optional[str] = Field(
        None,
        description="Twilio phone number for SMS"
    )
    
    # OSRM Route Server Settings
    osrm_server_url: str = Field(
        default="http://localhost:5000",
        description="OSRM route server URL"
    )
    osrm_profile: str = "driving"
    osrm_timeout: int = 30
    
    # Ride Settings
    max_detour_minutes: int = 5
    max_seats_per_vehicle: int = 4
    ride_timeout_minutes: int = 15
    otp_expire_minutes: int = 5
    
    # Matching Settings
    matching_radius_meters: int = 2000
    matching_buffer_minutes: int = 5
    
    # Modal Shift Settings
    bike_to_auto_threshold: int = 2
    bike_to_cab_threshold: int = 5
    auto_to_cab_threshold: int = 3
    # Dispatch & Matching Settings
    dispatch_radius_km: float = 5.0
    dispatch_timeout_seconds: int = 30
    max_dispatch_attempts: int = 3
    matching_radius_meters: int = 2000
    matching_buffer_minutes: int = 5
    # Gemini AI Safety Copilot Settings
    gemini_api_key: Optional[str] = Field(
        None,
        description="Google Gemini API key for multimodal incident triage & safety copilot"
    )
    gemini_model_name: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model used for text/audio/image incident triage"
    )
    gemini_vision_model_name: str = Field(
        default="gemini-1.5-pro",
        description="Gemini model used for multimodal (image/audio) safety analysis"
    )
    gemini_timeout_seconds: int = 20
    gemini_max_retries: int = 2

    # Consensus Voting Settings
    consensus_vote_timeout_seconds: int = 15
    consensus_min_approval_ratio: float = 0.5
    # Payment Settings
    default_currency: str = "INR"
    # Fare Engine Settings
    base_fare_bike: float = 15.0
    base_fare_auto: float = 25.0
    base_fare_cab: float = 45.0
    per_km_rate_bike: float = 5.0
    per_km_rate_auto: float = 8.0
    per_km_rate_cab: float = 12.0
    per_minute_rate: float = 1.0
    surge_max_multiplier: float = 2.5
    detour_surcharge_per_minute: float = 2.0
    platform_fee_percent: float = 5.0

    # Guardian Mode / Emergency Settings
    guardian_mode_ping_interval_seconds: int = 10
    sos_siren_duration_seconds: int = 30
    emergency_contact_max_count: int = 5
    low_light_lux_threshold: float = 15.0
    
    # CORS Settings
    cors_origins: list = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    
    # AI Engine Settings
    ai_engine_path: str = Field(
        default="../ai_engine",
        description="Path to AI engine directory"
    )
    risk_model_path: str = Field(
        default="ai_engine/models/risk_engine.onnx",
        description="Path to risk model ONNX file"
    )
    
    # Telemetry Settings
    telemetry_batch_size: int = 100
    telemetry_flush_interval_seconds: int = 10
    
    # Logging Settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql+asyncpg://", "postgresql://")):
            raise ValueError("Database URL must use postgresql+asyncpg driver")
        return v
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings
    """
    return Settings()


# For direct access
settings = get_settings()


if __name__ == "__main__":
    # Test settings loading
    print("Testing Settings Configuration...")
    print(f"App Name: {settings.app_name}")
    print(f"Environment: {settings.environment}")
    print(f"Database URL: {settings.database_url[:20]}...")
    print(f"OSRM Server: {settings.osrm_server_url}")
    print(f"Max Detour: {settings.max_detour_minutes} minutes")
    print("\nSettings loaded successfully!")
