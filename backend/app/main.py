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
import sys
import os

# Add ai_engine to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# Import routers
from .api.v1 import auth, rides, liveness, risk, gemini, consensus, fare, emergency, driver, dispatch, payment, notification, rating

# Import database and config
from backend.app.api.v1.core.database import init_db, close_db, check_db_connection
from backend.app.api.v1.core.config import get_settings

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Handles:
    - Database initialization
    - AI model preloading
    - Connection pool setup
    """
    # Startup
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
        print(f"Warning: Database initialization failed: {e}")
        print("API will attempt to connect on first request")
    
    # Check database connection
    print("\nChecking database connection...")
    db_healthy = await check_db_connection()
    if db_healthy:
        print("Database connection: HEALTHY")
    else:
        print("Database connection: UNHEALTHY")
    
    # Load AI Risk Engine models
    print("\nLoading AI Risk Engine models...")
    try:
        from backend.app.api.v1.risk import get_predictor
        get_predictor()
        print("Risk Engine models loaded successfully")
    except Exception as e:
        print(f"Warning: Could not load Risk Engine models: {e}")
        print("Risk evaluation endpoints will attempt to load models on first request")
    
    # Load Liveness Detection detectors
    print("\nLoading Liveness Detection detectors...")
    try:
        from backend.app.api.v1.liveness import get_liveness_detector, get_fallback_handler
        get_liveness_detector()
        get_fallback_handler()
        print("Liveness Detection detectors loaded successfully")
    except Exception as e:
        print(f"Warning: Could not load Liveness Detection detectors: {e}")
        print("Liveness endpoints will attempt to load detectors on first request")
    
    print("\n" + "=" * 60)
    print("OptimalRide Backend API started successfully!")
    print("=" * 60)
    
    yield
    
    # Shutdown
    print("\nShutting down OptimalRide Backend API...")
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
            "Driver Liveness Detection",
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
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": "2026-09-27T00:00:00Z"
    }


@app.get("/api/v1/health")
async def api_health():
    """Detailed API health check."""
    components = {
        "database": await check_db_connection(),
        "risk_engine": True,  # Will be checked dynamically
        "liveness_detection": True  # Will be checked dynamically
    }
    
    all_healthy = all(components.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
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
