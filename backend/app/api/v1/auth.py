"""
Authentication API Endpoints with JWT and OTP

This module implements:
- Passenger & Driver registration/login
- JWT token generation and validation
- Phone OTP dispatch via SMS/FCM
- Token refresh mechanism

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Literal
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext

from backend.app.api.v1.core.database import get_db
from backend.app.api.v1.core.config import get_settings
from backend.app.db.models import User, UserRole
from backend.app.services.sms_service import sms_service
from backend.app.services.notification import notification_manager

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Get settings
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token security
security = HTTPBearer()


# Pydantic Schemas
class UserRegistration(BaseModel):
    """User registration request schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    phone: str = Field(..., min_length=10, max_length=20, description="Phone number with country code")
    role: Literal["passenger", "driver"] = Field(..., description="User role")
    age: Optional[int] = Field(None, ge=18, le=100, description="User age")
    gender: Optional[str] = Field(None, description="User gender")
    fcm_token: Optional[str] = Field(None, description="FCM token for push notifications")


class UserLogin(BaseModel):
    """User login request schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    phone: str = Field(..., min_length=10, max_length=20, description="Phone number")
    role: Literal["passenger", "driver"] = Field(..., description="User role")


class OTPRequest(BaseModel):
    """OTP request schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    phone: str = Field(..., min_length=10, max_length=20, description="Phone number")
    delivery_method: Literal["sms", "fcm"] = Field("sms", description="OTP delivery method")


class OTPVerification(BaseModel):
    """OTP verification schema."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    phone: str = Field(..., min_length=10, max_length=20, description="Phone number")
    otp: str = Field(..., min_length=6, max_length=6, description="OTP code")
    role: Literal["passenger", "driver"] = Field(..., description="User role")


class TokenResponse(BaseModel):
    """Token response schema."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: Optional[dict] = Field(None, description="User information")


class UserResponse(BaseModel):
    """User response schema."""
    
    id: int = Field(..., description="User ID")
    phone: str = Field(..., description="Phone number")
    role: str = Field(..., description="User role")
    age: Optional[int] = Field(None, description="User age")
    gender: Optional[str] = Field(None, description="User gender")
    rating: float = Field(..., description="User rating")
    is_active: bool = Field(..., description="Account status")


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    
    refresh_token: str = Field(..., description="Refresh token")


# JWT Functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload data
        expires_delta: Custom expiration time
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire, "type": "access"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create JWT refresh token.
    
    Args:
        data: Payload data
        
    Returns:
        JWT refresh token string
    """
    to_encode = data.copy()
    
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Verify JWT token.
    
    Args:
        token: JWT token string
        token_type: Expected token type (access/refresh)
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}"
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Get current user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        User payload from token
        
    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    return payload


# Database Functions
async def get_user_by_phone(
    db: AsyncSession,
    phone: str
) -> Optional[User]:
    """
    Get user by phone number.
    
    Args:
        db: Database session
        phone: Phone number
        
    Returns:
        User object or None
    """
    result = await db.execute(
        select(User).where(User.phone == phone)
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    phone: str,
    role: UserRole,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    fcm_token: Optional[str] = None
) -> User:
    """
    Create new user.
    
    Args:
        db: Database session
        phone: Phone number
        role: User role
        age: User age
        gender: User gender
        fcm_token: FCM token
        
    Returns:
        Created user object
    """
    user = User(
        phone=phone,
        role=role,
        age=age,
        gender=gender,
        fcm_token=fcm_token,
        rating=5.0,
        is_active=True
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


# API Endpoints
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistration,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user (passenger or driver).
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Created user information
    """
    try:
        # Check if user already exists
        existing_user = await get_user_by_phone(db, user_data.phone)
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this phone number already exists"
            )
        
        # Create new user
        user = await create_user(
            db,
            user_data.phone,
            UserRole(user_data.role),
            user_data.age,
            user_data.gender,
            user_data.fcm_token
        )
        
        return UserResponse(
            id=user.id,
            phone=user.phone,
            role=user.role.value,
            age=user.age,
            gender=user.gender,
            rating=user.rating,
            is_active=user.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/request-otp")
async def request_otp(
    otp_request: OTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request OTP for phone verification.
    
    Sends OTP via SMS or FCM based on delivery method preference.
    
    Args:
        otp_request: OTP request data
        db: Database session
        
    Returns:
        OTP delivery status
    """
    try:
        # Check if user exists
        user = await get_user_by_phone(db, otp_request.phone)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please register first."
            )
        
        # Send OTP
        if otp_request.delivery_method == "sms":
            result = await sms_service.send_otp(otp_request.phone, user.id)
        elif otp_request.delivery_method == "fcm" and user.fcm_token:
            # In production, send via FCM
            result = await sms_service.send_otp(otp_request.phone, user.id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid delivery method or FCM token not available"
            )
        
        return {
            "success": result.get("success", False),
            "message": "OTP sent successfully" if result.get("success") else "Failed to send OTP",
            "expires_in_minutes": settings.otp_expire_minutes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OTP request failed: {str(e)}"
        )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    otp_data: OTPVerification,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and generate JWT tokens.
    
    Args:
        otp_data: OTP verification data
        db: Database session
        
    Returns:
        JWT access and refresh tokens
    """
    try:
        # Get user
        user = await get_user_by_phone(db, otp_data.phone)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify role matches
        if user.role.value != otp_data.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role mismatch"
            )
        
        # In production, verify against stored OTP
        # For now, accept any 6-digit OTP
        if len(otp_data.otp) != 6 or not otp_data.otp.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP format"
            )
        
        # Generate tokens
        token_data = {
            "sub": str(user.id),
            "phone": user.phone,
            "role": user.role.value
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user={
                "id": user.id,
                "phone": user.phone,
                "role": user.role.value,
                "age": user.age,
                "gender": user.gender,
                "rating": user.rating
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OTP verification failed: {str(e)}"
        )


@router.post("/refresh-token", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_data: Refresh token data
        db: Database session
        
    Returns:
        New access and refresh tokens
    """
    try:
        # Verify refresh token
        payload = verify_token(refresh_data.refresh_token, "refresh")
        
        # Get user
        user_id = int(payload.get("sub"))
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new tokens
        token_data = {
            "sub": str(user.id),
            "phone": user.phone,
            "role": user.role.value
        }
        
        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user={
                "id": user.id,
                "phone": user.phone,
                "role": user.role.value,
                "age": user.age,
                "gender": user.gender,
                "rating": user.rating
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user information.
    
    Args:
        current_user: Current user from JWT token
        db: Database session
        
    Returns:
        Current user information
    """
    try:
        user_id = int(current_user.get("sub"))
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=user.id,
            phone=user.phone,
            role=user.role.value,
            age=user.age,
            gender=user.gender,
            rating=user.rating,
            is_active=user.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user)
):
    """
    Logout current user.
    
    In a production system, this would invalidate the token
    in a token blacklist or Redis cache.
    
    Args:
        current_user: Current user from JWT token
        
    Returns:
        Logout confirmation
    """
    # In production, add token to blacklist
    return {
        "message": "Logged out successfully",
        "timestamp": datetime.now().isoformat()
    }
