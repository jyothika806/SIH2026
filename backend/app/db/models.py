"""
SQLAlchemy ORM Models with PostGIS Support

This module defines:
- User: Passenger and Driver accounts
- Ride: Ride lifecycle with spatial data
- MidRouteRequest: Mid-route pickup requests
- Telemetry: Driver telemetry data

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date,
    ForeignKey, Enum as SQLEnum, Text, JSON, func
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
import enum
from datetime import datetime
from typing import Optional, List

from backend.app.api.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class VehicleType(str, enum.Enum):
    """Vehicle type enumeration."""
    BIKE = "bike"
    AUTO = "auto"
    CAB = "cab"


class RideStatus(str, enum.Enum):
    """Ride status enumeration."""
    REQUESTED = "requested"
    SEARCHING = "searching"
    DRIVER_ASSIGNED = "driver_assigned"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class MidRouteStatus(str, enum.Enum):
    """Mid-route request status enumeration."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class User(Base):
    """
    User model for passengers and drivers.
    
    Attributes:
        id: Unique user identifier
        phone: Phone number (unique)
        role: User role (passenger/driver/admin)
        fcm_token: Firebase Cloud Messaging token
        age: User age
        gender: User gender
        rating: Average rating
        is_active: Account status
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.PASSENGER)
    fcm_token = Column(String(512), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    rating = Column(Float, default=5.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    rides_as_driver = relationship("Ride", back_populates="driver", foreign_keys="Ride.driver_id")
    rides_as_passenger = relationship("Ride", back_populates="passenger", foreign_keys="Ride.passenger_id")
    mid_route_requests = relationship("MidRouteRequest", back_populates="passenger")
    
    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone}, role={self.role})>"


class Ride(Base):
    """
    Ride model with spatial data.
    
    Attributes:
        id: Unique ride identifier
        driver_id: Driver user ID
        passenger_id: Primary passenger user ID
        vehicle_type: Type of vehicle
        pickup_point: Pickup location (Point geometry)
        dropoff_point: Dropoff location (Point geometry)
        route_geometry: Complete route as LineString
        seats_total: Total seats available
        seats_occupied: Currently occupied seats
        status: Current ride status
        otp: One-time password for ride start
        otp_unlocked: Whether OTP is unlocked after liveness verification
        otp_expires_at: OTP expiration time
        estimated_duration: Estimated ride duration in minutes
        estimated_distance: Estimated ride distance in meters
        actual_duration: Actual ride duration in minutes
        actual_distance: Actual ride distance in meters
        fare: Ride fare
        created_at: Ride creation timestamp
        updated_at: Last update timestamp
        started_at: Ride start timestamp
        completed_at: Ride completion timestamp
    """
    
    __tablename__ = "rides"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_type = Column(SQLEnum(VehicleType), nullable=False)
    
    # Spatial data
    pickup_point = Column(Geometry('POINT', srid=4326), nullable=False)
    dropoff_point = Column(Geometry('POINT', srid=4326), nullable=False)
    route_geometry = Column(Geometry('LINESTRING', srid=4326), nullable=True)
    
    # Seat management
    seats_total = Column(Integer, default=4)
    seats_occupied = Column(Integer, default=1)
    
    # Status
    status = Column(SQLEnum(RideStatus), default=RideStatus.REQUESTED)
    
    # OTP
    otp = Column(String(6), nullable=True)
    otp_unlocked = Column(Boolean, default=False)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Estimates
    estimated_duration = Column(Integer, nullable=True)  # minutes
    estimated_distance = Column(Integer, nullable=True)  # meters
    
    # Actuals
    actual_duration = Column(Integer, nullable=True)  # minutes
    actual_distance = Column(Integer, nullable=True)  # meters
    
    # Fare
    fare = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional metadata
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    driver = relationship("User", back_populates="rides_as_driver", foreign_keys=[driver_id])
    passenger = relationship("User", back_populates="rides_as_passenger", foreign_keys=[passenger_id])
    mid_route_requests = relationship("MidRouteRequest", back_populates="ride")
    telemetry_data = relationship("Telemetry", back_populates="ride")
    
    def __repr__(self):
        return f"<Ride(id={self.id}, status={self.status}, vehicle_type={self.vehicle_type})>"
    
    def to_dict(self) -> dict:
        """Convert ride to dictionary."""
        return {
            "id": self.id,
            "driver_id": self.driver_id,
            "passenger_id": self.passenger_id,
            "vehicle_type": self.vehicle_type.value,
            "seats_total": self.seats_total,
            "seats_occupied": self.seats_occupied,
            "status": self.status.value,
            "otp_unlocked": self.otp_unlocked,
            "estimated_duration": self.estimated_duration,
            "estimated_distance": self.estimated_distance,
            "fare": self.fare,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class MidRouteRequest(Base):
    """
    Mid-route pickup request model.
    
    Attributes:
        id: Unique request identifier
        ride_id: Parent ride ID
        passenger_id: Requesting passenger ID
        pickup_point: Pickup location (Point geometry)
        dropoff_point: Dropoff location (Point geometry)
        status: Request status
        detour_minutes: Estimated detour time in minutes
        consent_required: Whether passenger consent is required
        consent_responses: JSON object with passenger consent responses
        created_at: Request creation timestamp
        updated_at: Last update timestamp
        expires_at: Request expiration timestamp
    """
    
    __tablename__ = "mid_route_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Spatial data
    pickup_point = Column(Geometry('POINT', srid=4326), nullable=False)
    dropoff_point = Column(Geometry('POINT', srid=4326), nullable=False)
    
    # Status
    status = Column(SQLEnum(MidRouteStatus), default=MidRouteStatus.PENDING)
    
    # Detour calculation
    detour_minutes = Column(Float, nullable=True)
    
    # Consent management
    consent_required = Column(Boolean, default=True)
    consent_responses = Column(JSON, nullable=True)  # {"passenger_id": "accepted"/"rejected"}
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional metadata
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    ride = relationship("Ride", back_populates="mid_route_requests")
    passenger = relationship("User", back_populates="mid_route_requests")
    
    def __repr__(self):
        return f"<MidRouteRequest(id={self.id}, status={self.status}, ride_id={self.ride_id})>"


class Telemetry(Base):
    """
    Driver telemetry data model.
    
    Attributes:
        id: Unique telemetry entry identifier
        ride_id: Associated ride ID
        timestamp: Telemetry timestamp
        location: Current location (Point geometry)
        speed: Current speed in km/h
        heading: Current heading in degrees
        altitude: Current altitude in meters
        accuracy: Location accuracy in meters
        battery_level: Device battery level percentage
        harsh_braking: Harsh braking event count
        harsh_acceleration: Harsh acceleration event count
        speeding: Speeding event count
        metadata: Additional telemetry data
    """
    
    __tablename__ = "telemetry"
    
    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Location data
    location = Column(Geometry('POINT', srid=4326), nullable=False)
    speed = Column(Float, nullable=True)  # km/h
    heading = Column(Float, nullable=True)  # degrees
    altitude = Column(Float, nullable=True)  # meters
    accuracy = Column(Float, nullable=True)  # meters
    
    # Device data
    battery_level = Column(Integer, nullable=True)  # percentage
    
    # Safety events
    harsh_braking = Column(Integer, default=0)
    harsh_acceleration = Column(Integer, default=0)
    speeding = Column(Integer, default=0)
    
    # Additional metadata
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    ride = relationship("Ride", back_populates="telemetry_data")
    
    def __repr__(self):
        return f"<Telemetry(id={self.id}, ride_id={self.ride_id}, timestamp={self.timestamp})>"
    
    def to_dict(self) -> dict:
        """Convert telemetry to dictionary."""
        return {
            "id": self.id,
            "ride_id": self.ride_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "speed": self.speed,
            "heading": self.heading,
            "altitude": self.altitude,
            "accuracy": self.accuracy,
            "battery_level": self.battery_level,
            "harsh_braking": self.harsh_braking,
            "harsh_acceleration": self.harsh_acceleration,
            "speeding": self.speeding
        }


class ModalShiftSuggestion(Base):
    """
    Modal shift suggestion model.
    
    Attributes:
        id: Unique suggestion identifier
        source_ride_ids: List of source ride IDs to combine
        suggested_vehicle_type: Suggested vehicle type
        total_passengers: Total number of passengers
        estimated_savings: Estimated cost/time savings
        status: Suggestion status
        created_at: Suggestion creation timestamp
        expires_at: Suggestion expiration timestamp
    """
    
    __tablename__ = "modal_shift_suggestions"
    
    id = Column(Integer, primary_key=True, index=True)
    source_ride_ids = Column(JSON, nullable=False)  # List of ride IDs
    suggested_vehicle_type = Column(SQLEnum(VehicleType), nullable=False)
    total_passengers = Column(Integer, nullable=False)
    estimated_savings = Column(JSON, nullable=True)  # {"cost": float, "time": float}
    status = Column(String(20), default="pending")  # pending/accepted/rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<ModalShiftSuggestion(id={self.id}, vehicle_type={self.suggested_vehicle_type})>"


class OtpLog(Base):
    """
    OTP delivery log model.
    
    Attributes:
        id: Unique log entry identifier
        phone: Phone number
        otp: OTP code
        delivery_method: Delivery method (sms/fcm/push)
        delivery_status: Delivery status
        attempt_count: Number of delivery attempts
        created_at: Log creation timestamp
        expires_at: OTP expiration timestamp
    """
    
    __tablename__ = "otp_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), nullable=False, index=True)
    otp = Column(String(6), nullable=False)
    delivery_method = Column(String(20), nullable=False)  # sms/fcm/push
    delivery_status = Column(String(20), default="pending")  # pending/sent/failed
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<OtpLog(id={self.id}, phone={self.phone}, status={self.delivery_status})>"


class ConsensusVote(Base):
    """
    Consensus voting session model.
    
    Attributes:
        id: Unique vote identifier
        vote_id: External vote ID from consensus service
        ride_id: Associated ride ID
        proposal_type: Type of proposal
        proposal_data: JSON proposal data
        eligible_voters: JSON list of eligible passenger IDs
        votes: JSON dict of passenger_id -> vote
        status: Vote status
        created_at: Vote creation timestamp
        expires_at: Vote expiration timestamp
        resolved_at: Vote resolution timestamp
    """
    
    __tablename__ = "consensus_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    vote_id = Column(String(100), unique=True, nullable=False, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    proposal_type = Column(String(50), nullable=False)
    proposal_data = Column(JSON, nullable=True)
    eligible_voters = Column(JSON, nullable=False)
    votes = Column(JSON, nullable=True)
    status = Column(String(20), default="pending")  # pending/approved/rejected/timeout
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<ConsensusVote(id={self.id}, vote_id={self.vote_id}, status={self.status})>"


class FareSplit(Base):
    """
    Fare split allocation model.
    
    Attributes:
        id: Unique split identifier
        ride_id: Associated ride ID
        passenger_id: Passenger ID
        share_percentage: Share percentage
        share_amount: Share amount in currency
        is_primary: Whether this is the primary passenger
        payment_status: Payment status
        created_at: Split creation timestamp
        paid_at: Payment completion timestamp
    """
    
    __tablename__ = "fare_splits"
    
    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_percentage = Column(Float, nullable=False)
    share_amount = Column(Float, nullable=False)
    is_primary = Column(Boolean, default=False)
    payment_status = Column(String(20), default="pending")  # pending/paid/failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<FareSplit(id={self.id}, passenger_id={self.passenger_id}, amount={self.share_amount})>"


class EmergencyIncident(Base):
    """
    Emergency incident model.
    
    Attributes:
        id: Unique incident identifier
        incident_id: External incident ID from emergency service
        ride_id: Associated ride ID
        user_id: User who triggered/reported incident
        user_role: User role (passenger/driver)
        emergency_type: Type of emergency
        severity: Severity level
        location: Incident location (Point geometry)
        description: Incident description
        metadata: Additional incident data
        resolved: Whether incident is resolved
        resolved_at: Resolution timestamp
        created_at: Incident creation timestamp
    """
    
    __tablename__ = "emergency_incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(100), unique=True, nullable=False, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_role = Column(String(20), nullable=False)
    emergency_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    location = Column(Geometry('POINT', srid=4326), nullable=False)
    description = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<EmergencyIncident(id={self.id}, type={self.emergency_type}, severity={self.severity})>"


class GuardianModeSession(Base):
    """
    Guardian Mode session model.
    
    Attributes:
        id: Unique session identifier
        session_id: External session ID from emergency service
        ride_id: Associated ride ID
        user_id: User who started Guardian Mode
        emergency_contacts: JSON list of emergency contacts
        started_at: Session start timestamp
        last_ping: Last location ping timestamp
        ping_interval_seconds: Ping interval in seconds
        active: Whether session is active
        ended_at: Session end timestamp
    """
    
    __tablename__ = "guardian_mode_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emergency_contacts = Column(JSON, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_ping = Column(DateTime(timezone=True), server_default=func.now())
    ping_interval_seconds = Column(Integer, default=10)
    active = Column(Boolean, default=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<GuardianModeSession(id={self.id}, session_id={self.session_id}, active={self.active})>"


class DriverProfile(Base):
    """
    Driver profile model with vehicle and document information.
    
    Attributes:
        id: Unique profile identifier
        user_id: Associated user ID
        license_number: Driver's license number
        license_expiry: License expiration date
        vehicle_type: Type of vehicle (bike/auto/cab)
        vehicle_number: Vehicle registration number
        vehicle_model: Vehicle model name
        vehicle_color: Vehicle color
        vehicle_year: Vehicle manufacturing year
        is_verified: Whether profile is verified
        verification_status: Verification status
        verification_date: Verification timestamp
        total_rides: Total completed rides
        total_earnings: Total earnings
        rating: Driver rating
        is_online: Whether driver is online
        current_location: Current location (Point geometry)
        last_location_update: Last location update timestamp
    """
    
    __tablename__ = "driver_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    license_number = Column(String(50), nullable=False)
    license_expiry = Column(Date, nullable=False)
    vehicle_type = Column(String(20), nullable=False)
    vehicle_number = Column(String(20), unique=True, nullable=False)
    vehicle_model = Column(String(100), nullable=False)
    vehicle_color = Column(String(50), nullable=False)
    vehicle_year = Column(Integer, nullable=False)
    is_verified = Column(Boolean, default=False)
    verification_status = Column(String(20), default="pending")  # pending/verified/rejected
    verification_date = Column(DateTime(timezone=True), nullable=True)
    total_rides = Column(Integer, default=0)
    total_earnings = Column(Float, default=0.0)
    rating = Column(Float, default=5.0)
    is_online = Column(Boolean, default=False)
    current_location = Column(Geometry('POINT', srid=4326))
    last_location_update = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<DriverProfile(id={self.id}, user_id={self.user_id}, vehicle_number={self.vehicle_number})>"


class DocumentVerification(Base):
    """
    Document verification model for driver onboarding.
    
    Attributes:
        id: Unique verification record identifier
        user_id: Associated user ID
        document_type: Type of document (license/vehicle_rc/insurance/aadhar)
        document_url: URL to stored document
        document_hash: Hash of document for integrity
        verification_status: Verification status
        verified_by: Admin user who verified
        verified_at: Verification timestamp
        rejection_reason: Reason for rejection if any
        created_at: Document upload timestamp
    """
    
    __tablename__ = "document_verifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(String(50), nullable=False)  # license/vehicle_rc/insurance/aadhar
    document_url = Column(String(500), nullable=False)
    document_hash = Column(String(256), nullable=True)
    verification_status = Column(String(20), default="pending")  # pending/verified/rejected
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<DocumentVerification(id={self.id}, user_id={self.user_id}, type={self.document_type}, status={self.verification_status})>"


class RideRating(Base):
    """
    Ride rating and review model.
    
    Attributes:
        id: Unique rating identifier
        ride_id: Associated ride ID
        rater_id: User who gave the rating
        rated_user_id: User being rated
        rating: Rating score (1-5)
        review: Review text
        rating_category: Category of rating (safety/punctuality/behavior/overall)
        created_at: Rating timestamp
    """
    
    __tablename__ = "ride_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    rater_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rated_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    review = Column(Text, nullable=True)
    rating_category = Column(String(50), default="overall")  # safety/punctuality/behavior/overall
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<RideRating(id={self.id}, ride_id={self.ride_id}, rating={self.rating})>"


class Wallet(Base):
    """
    User wallet model for in-app payments.
    
    Attributes:
        id: Unique wallet identifier
        user_id: Associated user ID
        balance: Current wallet balance
        currency: Currency code (default INR)
        is_active: Whether wallet is active
        created_at: Wallet creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0.0)
    currency = Column(String(3), default="INR")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Wallet(id={self.id}, user_id={self.user_id}, balance={self.balance})>"


class Transaction(Base):
    """
    Transaction model for wallet operations.
    
    Attributes:
        id: Unique transaction identifier
        wallet_id: Associated wallet ID
        transaction_type: Type of transaction (credit/debit)
        amount: Transaction amount
        description: Transaction description
        reference_id: External reference ID (ride_id, etc.)
        status: Transaction status
        created_at: Transaction timestamp
    """
    
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # credit/debit
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    reference_id = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # pending/completed/failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.transaction_type}, amount={self.amount})>"


class Notification(Base):
    """
    Notification model for FCM and in-app notifications.
    
    Attributes:
        id: Unique notification identifier
        user_id: Recipient user ID
        title: Notification title
        body: Notification body
        type: Notification type
        data: Additional data payload
        read: Whether notification has been read
        fcm_sent: Whether FCM push was sent
        fcm_message_id: FCM message ID
        created_at: Notification timestamp
    """
    
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # ride/otp/emergency/promo
    data = Column(JSON, nullable=True)
    read = Column(Boolean, default=False)
    fcm_sent = Column(Boolean, default=False)
    fcm_message_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type})>"
