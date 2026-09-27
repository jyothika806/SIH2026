-- OptimalRide Database Schema
-- PostgreSQL with PostGIS extension for spatial data
-- SIH 2026 Problem Statement ID 26203

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE vehicle_type AS ENUM ('bike', 'auto', 'cab');
CREATE TYPE user_role AS ENUM ('passenger', 'driver', 'admin');
CREATE TYPE ride_status AS ENUM ('requested', 'searching', 'driver_assigned', 'arrived', 'in_progress', 'completed', 'cancelled');
CREATE TYPE vote_status AS ENUM ('pending', 'approved', 'rejected', 'timeout');
CREATE TYPE emergency_type AS ENUM ('sos_button', 'guardian_mode', 'route_deviation', 'unusual_stop', 'harsh_braking', 'speeding', 'passenger_report', 'driver_report');
CREATE TYPE emergency_severity AS ENUM ('low', 'medium', 'high', 'critical');

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    role user_role NOT NULL DEFAULT 'passenger',
    fcm_token VARCHAR(255),
    age INTEGER,
    gender VARCHAR(10),
    rating DECIMAL(3, 2) DEFAULT 5.00,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes on users
CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Rides table with PostGIS geometry
CREATE TABLE rides (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES users(id),
    passenger_id INTEGER REFERENCES users(id),
    vehicle_type vehicle_type NOT NULL,
    seats_total INTEGER NOT NULL DEFAULT 1,
    seats_occupied INTEGER NOT NULL DEFAULT 0,
    status ride_status NOT NULL DEFAULT 'requested',
    otp_unlocked BOOLEAN DEFAULT FALSE,
    
    -- Spatial data
    pickup_lat DECIMAL(10, 8),
    pickup_lon DECIMAL(11, 8),
    pickup_location GEOMETRY(POINT, 4326),
    dropoff_lat DECIMAL(10, 8),
    dropoff_lon DECIMAL(11, 8),
    dropoff_location GEOMETRY(POINT, 4326),
    
    -- Route corridor for geofencing
    route_corridor GEOMETRY(LINESTRING, 4326),
    
    -- Fare and timing
    estimated_duration INTEGER, -- in minutes
    estimated_distance INTEGER, -- in meters
    fare DECIMAL(10, 2),
    
    -- OTP
    otp_code VARCHAR(6),
    otp_expires_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial indexes
CREATE INDEX idx_rides_pickup_location ON rides USING GIST(pickup_location);
CREATE INDEX idx_rides_dropoff_location ON rides USING GIST(dropoff_location);
CREATE INDEX idx_rides_route_corridor ON rides USING GIST(route_corridor);

-- Create other indexes
CREATE INDEX idx_rides_driver_id ON rides(driver_id);
CREATE INDEX idx_rides_passenger_id ON rides(passenger_id);
CREATE INDEX idx_rides_status ON rides(status);
CREATE INDEX idx_rides_vehicle_type ON rides(vehicle_type);
CREATE INDEX idx_rides_created_at ON rides(created_at);

-- Mid-route requests table
CREATE TABLE mid_route_requests (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    requesting_passenger_id INTEGER REFERENCES users(id),
    pickup_lat DECIMAL(10, 8) NOT NULL,
    pickup_lon DECIMAL(11, 8) NOT NULL,
    pickup_location GEOMETRY(POINT, 4326),
    detour_minutes INTEGER NOT NULL,
    consent_given BOOLEAN DEFAULT FALSE,
    consent_given_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_mid_route_ride_id ON mid_route_requests(ride_id);
CREATE INDEX idx_mid_route_pickup_location ON mid_route_requests USING GIST(pickup_location);

-- Telemetry table for ride tracking
CREATE TABLE telemetry (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    location GEOMETRY(POINT, 4326),
    speed DECIMAL(6, 2), -- km/h
    heading DECIMAL(5, 2), -- degrees
    altitude DECIMAL(8, 2), -- meters
    accuracy DECIMAL(6, 2), -- meters
    battery_level INTEGER, -- percentage
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_telemetry_ride_id ON telemetry(ride_id);
CREATE INDEX idx_telemetry_user_id ON telemetry(user_id);
CREATE INDEX idx_telemetry_location ON telemetry USING GIST(location);
CREATE INDEX idx_telemetry_timestamp ON telemetry(timestamp);

-- Modal shift suggestions table
CREATE TABLE modal_shift_suggestions (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    original_vehicle_type vehicle_type NOT NULL,
    suggested_vehicle_type vehicle_type NOT NULL,
    reason TEXT NOT NULL,
    estimated_savings DECIMAL(10, 2),
    accepted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_modal_shift_ride_id ON modal_shift_suggestions(ride_id);

-- OTP logs table
CREATE TABLE otp_logs (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) NOT NULL,
    otp VARCHAR(6) NOT NULL,
    delivery_method VARCHAR(20) NOT NULL, -- sms/fcm/push
    delivery_status VARCHAR(20) DEFAULT 'pending', -- pending/sent/failed
    attempt_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX idx_otp_logs_phone ON otp_logs(phone);
CREATE INDEX idx_otp_logs_created_at ON otp_logs(created_at);

-- Consensus votes table
CREATE TABLE consensus_votes (
    id SERIAL PRIMARY KEY,
    vote_id VARCHAR(100) UNIQUE NOT NULL,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    proposal_type VARCHAR(50) NOT NULL,
    proposal_data JSONB,
    eligible_voters JSONB NOT NULL,
    votes JSONB,
    status vote_status DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX idx_consensus_votes_vote_id ON consensus_votes(vote_id);
CREATE INDEX idx_consensus_votes_ride_id ON consensus_votes(ride_id);
CREATE INDEX idx_consensus_votes_status ON consensus_votes(status);

-- Fare splits table
CREATE TABLE fare_splits (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    passenger_id INTEGER REFERENCES users(id),
    share_percentage DECIMAL(5, 2) NOT NULL,
    share_amount DECIMAL(10, 2) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    payment_status VARCHAR(20) DEFAULT 'pending', -- pending/paid/failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX idx_fare_splits_ride_id ON fare_splits(ride_id);
CREATE INDEX idx_fare_splits_passenger_id ON fare_splits(passenger_id);
CREATE INDEX idx_fare_splits_payment_status ON fare_splits(payment_status);

-- Emergency incidents table
CREATE TABLE emergency_incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) UNIQUE NOT NULL,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    user_role VARCHAR(20) NOT NULL,
    emergency_type emergency_type NOT NULL,
    severity emergency_severity NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    description TEXT,
    metadata JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_emergency_incidents_incident_id ON emergency_incidents(incident_id);
CREATE INDEX idx_emergency_incidents_ride_id ON emergency_incidents(ride_id);
CREATE INDEX idx_emergency_incidents_user_id ON emergency_incidents(user_id);
CREATE INDEX idx_emergency_incidents_location ON emergency_incidents USING GIST(location);
CREATE INDEX idx_emergency_incidents_severity ON emergency_incidents(severity);
CREATE INDEX idx_emergency_incidents_resolved ON emergency_incidents(resolved);

-- Guardian mode sessions table
CREATE TABLE guardian_mode_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    ride_id INTEGER REFERENCES rides(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id),
    emergency_contacts JSONB NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_ping TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ping_interval_seconds INTEGER DEFAULT 10,
    active BOOLEAN DEFAULT TRUE,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX idx_guardian_sessions_session_id ON guardian_mode_sessions(session_id);
CREATE INDEX idx_guardian_sessions_ride_id ON guardian_mode_sessions(ride_id);
CREATE INDEX idx_guardian_sessions_user_id ON guardian_mode_sessions(user_id);
CREATE INDEX idx_guardian_sessions_active ON guardian_mode_sessions(active);

-- Driver profiles table
CREATE TABLE driver_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) NOT NULL,
    license_number VARCHAR(50) NOT NULL,
    license_expiry DATE NOT NULL,
    vehicle_type VARCHAR(20) NOT NULL,
    vehicle_number VARCHAR(20) UNIQUE NOT NULL,
    vehicle_model VARCHAR(100) NOT NULL,
    vehicle_color VARCHAR(50) NOT NULL,
    vehicle_year INTEGER NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_status VARCHAR(20) DEFAULT 'pending',
    verification_date TIMESTAMP WITH TIME ZONE,
    total_rides INTEGER DEFAULT 0,
    total_earnings DECIMAL(10, 2) DEFAULT 0.00,
    rating DECIMAL(3, 2) DEFAULT 5.00,
    is_online BOOLEAN DEFAULT FALSE,
    current_location GEOMETRY(POINT, 4326),
    last_location_update TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_driver_profiles_user_id ON driver_profiles(user_id);
CREATE INDEX idx_driver_profiles_vehicle_type ON driver_profiles(vehicle_type);
CREATE INDEX idx_driver_profiles_is_online ON driver_profiles(is_online);
CREATE INDEX idx_driver_profiles_is_verified ON driver_profiles(is_verified);
CREATE INDEX idx_driver_profiles_current_location ON driver_profiles USING GIST(current_location);

-- Document verifications table
CREATE TABLE document_verifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    document_url VARCHAR(500) NOT NULL,
    document_hash VARCHAR(256),
    verification_status VARCHAR(20) DEFAULT 'pending',
    verified_by INTEGER REFERENCES users(id),
    verified_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_document_verifications_user_id ON document_verifications(user_id);
CREATE INDEX idx_document_verifications_document_type ON document_verifications(document_type);
CREATE INDEX idx_document_verifications_status ON document_verifications(verification_status);

-- Ride ratings table
CREATE TABLE ride_ratings (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER REFERENCES rides(id) NOT NULL,
    rater_id INTEGER REFERENCES users(id) NOT NULL,
    rated_user_id INTEGER REFERENCES users(id) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    review TEXT,
    rating_category VARCHAR(50) DEFAULT 'overall',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_ride_ratings_ride_id ON ride_ratings(ride_id);
CREATE INDEX idx_ride_ratings_rater_id ON ride_ratings(rater_id);
CREATE INDEX idx_ride_ratings_rated_user_id ON ride_ratings(rated_user_id);
CREATE INDEX idx_ride_ratings_rating ON ride_ratings(rating);

-- Wallets table
CREATE TABLE wallets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) NOT NULL,
    balance DECIMAL(10, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'INR',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_wallets_user_id ON wallets(user_id);
CREATE INDEX idx_wallets_is_active ON wallets(is_active);

-- Transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    wallet_id INTEGER REFERENCES wallets(id) NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    description TEXT,
    reference_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_transactions_wallet_id ON transactions(wallet_id);
CREATE INDEX idx_transactions_reference_id ON transactions(reference_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- Notifications table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    data JSONB,
    read BOOLEAN DEFAULT FALSE,
    fcm_sent BOOLEAN DEFAULT FALSE,
    fcm_message_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_read ON notifications(read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- Create trigger function for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rides_updated_at BEFORE UPDATE ON rides
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create trigger to populate geometry columns from lat/lon
CREATE OR REPLACE FUNCTION update_pickup_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.pickup_lat IS NOT NULL AND NEW.pickup_lon IS NOT NULL THEN
        NEW.pickup_location = ST_SetSRID(ST_MakePoint(NEW.pickup_lon, NEW.pickup_lat), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_rides_pickup_location BEFORE INSERT OR UPDATE ON rides
    FOR EACH ROW EXECUTE FUNCTION update_pickup_location();

CREATE OR REPLACE FUNCTION update_dropoff_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.dropoff_lat IS NOT NULL AND NEW.dropoff_lon IS NOT NULL THEN
        NEW.dropoff_location = ST_SetSRID(ST_MakePoint(NEW.dropoff_lon, NEW.dropoff_lat), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_rides_dropoff_location BEFORE INSERT OR UPDATE ON rides
    FOR EACH ROW EXECUTE FUNCTION update_dropoff_location();

CREATE OR REPLACE FUNCTION update_mid_route_pickup_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.pickup_lat IS NOT NULL AND NEW.pickup_lon IS NOT NULL THEN
        NEW.pickup_location = ST_SetSRID(ST_MakePoint(NEW.pickup_lon, NEW.pickup_lat), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_mid_route_pickup_location BEFORE INSERT OR UPDATE ON mid_route_requests
    FOR EACH ROW EXECUTE FUNCTION update_mid_route_pickup_location();

CREATE OR REPLACE FUNCTION update_telemetry_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_telemetry_location BEFORE INSERT OR UPDATE ON telemetry
    FOR EACH ROW EXECUTE FUNCTION update_telemetry_location();

-- Insert sample data (optional)
-- INSERT INTO users (phone, role, age, gender, rating) VALUES
-- ('+919876543210', 'driver', 35, 'male', 4.5),
-- ('+919876543211', 'passenger', 28, 'female', 5.0);

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO optimal_ride_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO optimal_ride_user;
