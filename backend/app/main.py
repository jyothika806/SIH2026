"""
OptimalRide Backend - Main FastAPI Application

This is the main entry point for the OptimalRide backend service.
It includes all API routers, middleware configuration, and lifecycle handlers.

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
import sys
import os
import time

# Add ai_engine to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Import routers
from .api.v1 import auth, rides, liveness, risk, gemini, consensus, fare, emergency, driver, dispatch, payment, notification, rating, admin

# Import database and config
from backend.app.api.v1.core.database import AsyncSessionLocal, init_db, close_db, check_db_connection
from backend.app.api.v1.core.config import get_settings
from backend.app.core.log_redaction import install_sensitive_data_filter
from backend.app.core.redis import check_redis, close_redis
from backend.app.services.reservation_service import sweep_expired_lifecycle
from backend.app.services.rate_limiter import cleanup_expired_rate_limit_buckets
from backend.app.services.biometric_retention import cleanup_expired_biometric_templates
from cryptography.fernet import Fernet

# Get settings
settings = get_settings()
logger = logging.getLogger(__name__)


def validate_production_configuration() -> None:
    environment = settings.environment.lower()
    if settings.digilocker_enabled:
        raise RuntimeError("DigiLocker integration is disabled until authorized credentials and implementation are available")
    if settings.dev_otp_code and environment not in {"development", "test"}:
        raise RuntimeError("DEV_OTP_CODE is permitted only in development or test")
    if environment != "production":
        return
    required = {
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY"),
        "OTP_HMAC_KEY": settings.otp_hmac_key,
        "FERNET_KEY": settings.fernet_key,
        "LICENCE_HMAC_KEY": settings.licence_hmac_key,
        "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
        "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
        "TWILIO_PHONE_NUMBER": settings.twilio_phone_number,
        "REDIS_URL": settings.redis_url,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing production configuration: {', '.join(missing)}")
    if settings.dev_otp_code:
        raise RuntimeError("DEV_OTP_CODE must not be set in production")
    if settings.sms_provider.lower() != "twilio":
        raise RuntimeError("Production requires the configured Twilio SMS provider")
    if not settings.database_url.startswith(("postgresql+asyncpg://", "postgresql://")):
        raise RuntimeError("Production requires PostgreSQL with PostGIS")
    if len(settings.jwt_secret_key) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")
    if any(
        len(value or "") < 32
        for value in (settings.otp_hmac_key, settings.licence_hmac_key)
    ):
        raise RuntimeError("OTP_HMAC_KEY and LICENCE_HMAC_KEY must contain at least 32 characters")
    try:
        Fernet((settings.fernet_key or "").encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise RuntimeError("FERNET_KEY must be a valid Fernet key")


async def _sweeper_loop() -> None:
    last_rate_limit_cleanup = 0.0
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await sweep_expired_lifecycle(db)
                now_monotonic = time.monotonic()
                if (
                    now_monotonic - last_rate_limit_cleanup
                    >= settings.rate_limit_cleanup_interval_seconds
                ):
                    await cleanup_expired_rate_limit_buckets(db)
                    await cleanup_expired_biometric_templates(db)
                    last_rate_limit_cleanup = now_monotonic
                await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.error("Lifecycle sweeper failed (%s)", type(error).__name__)
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Handles:
    - Database initialization
    - AI model preloading
    - Connection pool setup
    """
    validate_production_configuration()
    install_sensitive_data_filter()
    sweeper_task = None
    print("=" * 60)
    print("Starting OptimalRide Backend API...")
    print("=" * 60)
    
    print(f"Environment: {settings.environment}")
    print(f"App Version: {settings.app_version}")
    
    # Initialize database
    print("\nInitializing database...")
    try:
        await init_db()
        print("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization failed (%s)", type(e).__name__)
        if settings.environment.lower() == "production":
            raise
    
    # Check database connection
    print("\nChecking database connection...")
    db_healthy = await check_db_connection()
    if db_healthy:
        print("Database connection: HEALTHY")
    else:
        print("Database connection: UNHEALTHY")
        if settings.environment.lower() == "production":
            raise RuntimeError("Production database is unavailable")

    redis_healthy = await check_redis()
    print(f"Redis connection: {'HEALTHY' if redis_healthy else 'UNAVAILABLE (DB rate-limit fallback active)'}")
    if settings.environment.lower() == "production" and not redis_healthy:
        raise RuntimeError("Production Redis rate limiting is unavailable")
    if db_healthy:
        sweeper_task = asyncio.create_task(_sweeper_loop())
    
    # Load AI Risk Engine models
    print("\nLoading AI Risk Engine models...")
    try:
        from backend.app.api.v1.risk import get_predictor
        get_predictor()
        print("Risk Engine models loaded successfully")
    except Exception as e:
        print(f"Warning: Could not load Risk Engine models: {e}")
        print("Risk evaluation endpoints will attempt to load models on first request")
    
    print("\nDriver identity verification is disabled until an authorized face model is configured.")
    
    print("\n" + "=" * 60)
    print("OptimalRide Backend API started successfully!")
    print("=" * 60)
    
    yield
    
    # Shutdown
    print("\nShutting down OptimalRide Backend API...")
    if sweeper_task is not None:
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass
    await close_redis()
    await close_db()
    print("Database connections closed")
    print("OptimalRide Backend API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="OptimalRide API",
    description="Backend API for OptimalRide - AI-powered ride-hailing safety platform with dynamic mid-route corridor matching",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.middleware("http")
async def prevent_sensitive_response_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(
        (
            "/api/v1/auth",
            "/api/v1/admin",
            "/api/v1/liveness",
            "/api/v1/driver",
            "/api/v1/rides",
            "/api/v1/dispatch",
        )
    ):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(rides.router, prefix="/api/v1", tags=["Rides"])
app.include_router(liveness.router, prefix="/api/v1", tags=["Liveness Detection"])
app.include_router(risk.router, prefix="/api/v1", tags=["Risk Assessment"])
app.include_router(gemini.router, prefix="/api/v1", tags=["Gemini AI Safety"])
app.include_router(consensus.router, prefix="/api/v1", tags=["Consensus Voting"])
app.include_router(fare.router, prefix="/api/v1", tags=["Fare & Payment"])
app.include_router(emergency.router, prefix="/api/v1", tags=["Emergency & Safety"])
app.include_router(driver.router, prefix="/api/v1", tags=["Driver Management"])
app.include_router(dispatch.router, prefix="/api/v1", tags=["Dispatch"])
app.include_router(payment.router, prefix="/api/v1", tags=["Payment"])
app.include_router(notification.router, prefix="/api/v1", tags=["Notification"])
app.include_router(rating.router, prefix="/api/v1", tags=["Rating"])
app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "OptimalRide API",
        "version": settings.app_version,
        "status": "operational",
        "environment": settings.environment,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
            "api": {
                "auth": "/api/v1/auth",
                "rides": "/api/v1/rides",
                "liveness": "/api/v1/liveness",
                "risk": "/api/v1/risk",
                "gemini": "/api/v1/gemini",
                "consensus": "/api/v1/consensus",
                "fare": "/api/v1/fare",
                "emergency": "/api/v1/emergency",
                "driver": "/api/v1/driver"
            }
        },
        "features": [
            "AI Risk Assessment",
            "Fail-closed driver identity verification",
            "Mid-Route Corridor Matching",
            "Modal Shift Aggregation",
            "Real-time WebSocket Tracking",
            "Gemini AI Incident Triage",
            "Consensus Voting Protocol",
            "Dynamic Fare Calculation",
            "Emergency SOS & Guardian Mode"
        ]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    db_healthy = await check_db_connection()
    redis_healthy = await check_redis()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "redis": "connected" if redis_healthy else "db-fallback",
        "timestamp": "2026-09-27T00:00:00Z"
    }


@app.get("/api/v1/health")
async def api_health():
    """Detailed API health check."""
    components = {
        "database": await check_db_connection(),
        "risk_engine": True,  # Will be checked dynamically
        "driver_identity_verification": False,
    }
    
    all_healthy = all(components.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
        "verification_limitation": "Authorized face identity model is not configured",
        "timestamp": "2026-09-27T00:00:00Z"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
