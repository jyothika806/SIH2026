import {
  ActiveRideListing,
  ConsolidationSuggestion,
  GeoLocation,
  PassengerProfile,
  RideState,
  TripRiskScore,
  VEHICLE_TYPES,
  VehicleMode,
  VehicleType,
} from '../types/commute';
import {
  bookRide,
  calculateFare,
  computeConsolidation,
  computeRiskScore,
  getRide,
  listActivePoolRides,
  pendingConsentForPassenger,
  requestMidRideJoin,
  streamPassengerStatus,
  submitConsent,
  triggerSos,
} from '../engine/commuteEngine';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export type { VehicleMode, VehicleType, GeoLocation as Location, PassengerProfile, TripRiskScore, ConsolidationSuggestion };

export interface RideBookingRequest {
  passengerId?: string;
  pickup: GeoLocation;
  dropoff: GeoLocation;
  vehicleType: VehicleMode;
  seatsRequired?: number;
}

export interface RideBookingResponse {
  success: boolean;
  rideId?: string;
  estimatedFare?: number;
  estimatedDuration?: number;
  driverId?: string;
  message?: string;
  error?: string;
}

export type RideStatus = RideState;

export interface SOSRequest {
  rideId?: string;
  passengerId?: string;
  location: GeoLocation;
  emergencyType?: string;
  description?: string;
}

export interface SOSResponse {
  success: boolean;
  incidentId?: string;
  emergencyContactsNotified?: boolean;
  locationShared?: boolean;
  securityCenterAlerted?: boolean;
  message?: string;
  error?: string;
}

export interface MidRideJoinRequest {
  rideId: string;
  requester?: PassengerProfile;
  pickup: GeoLocation;
  dropoff: GeoLocation;
}

async function postGateway(endpoint: string, body?: unknown, method = 'POST') {
  try {
    await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    /* FastAPI optional */
  }
}

class PassengerApi {
  async bookRide(request: RideBookingRequest): Promise<RideBookingResponse> {
    const local = bookRide(request);
    void postGateway('/api/v1/passenger/book', request);
    return local;
  }

  async getRideStatus(rideId: string): Promise<RideStatus> {
    const ride = getRide(rideId);
    if (!ride) throw new Error('Ride not found');
    void fetch(`${API_BASE_URL}/api/v1/passenger/status/${rideId}`).catch(() => undefined);
    return ride;
  }

  async streamStatus(rideId: string, location: GeoLocation) {
    const local = streamPassengerStatus(rideId, location);
    void postGateway('/api/v1/passenger/status', { rideId, location });
    return local;
  }

  async triggerSOS(request: SOSRequest): Promise<SOSResponse> {
    const local = triggerSos('passenger');
    void postGateway('/api/v1/passenger/sos', request);
    return local;
  }

  async requestMidRideJoin(request: MidRideJoinRequest) {
    const local = requestMidRideJoin(request.rideId, request.pickup, request.dropoff);
    void postGateway('/api/v1/passenger/mid-ride/request', request);
    return local;
  }

  async submitMidRideConsent(payload: {
    requestId: string;
    rideId: string;
    consent: 'accept' | 'reject';
    passengerId: string;
  }) {
    const local = submitConsent(payload.requestId, payload.passengerId, payload.consent);
    void postGateway('/api/v1/passenger/mid-ride/consent', payload);
    return local;
  }

  async getTripRiskScore(pickup: GeoLocation, dropoff: GeoLocation, vehicleType: VehicleMode): Promise<TripRiskScore> {
    const local = computeRiskScore(pickup, dropoff, vehicleType);
    const params = new URLSearchParams({
      pickupLat: String(pickup.lat),
      pickupLng: String(pickup.lng),
      dropoffLat: String(dropoff.lat),
      dropoffLng: String(dropoff.lng),
      vehicleType,
    });
    void fetch(`${API_BASE_URL}/api/v1/passenger/risk-score?${params}`).catch(() => undefined);
    return local;
  }

  async getConsolidationSuggestion(vehicleType: VehicleMode): Promise<ConsolidationSuggestion[]> {
    const local = computeConsolidation(vehicleType);
    void fetch(`${API_BASE_URL}/api/v1/passenger/consolidation?vehicleType=${vehicleType}`).catch(() => undefined);
    return local;
  }

  async listActiveRides(): Promise<ActiveRideListing[]> {
    return listActivePoolRides();
  }

  getPendingConsent(passengerId = 'passenger-001') {
    return pendingConsentForPassenger(passengerId);
  }

  getVehicleTypes(): VehicleType[] {
    return VEHICLE_TYPES;
  }

  calculateFare(vehicleType: VehicleMode, distanceKm: number, durationMinutes: number): number {
    return calculateFare(vehicleType, distanceKm, durationMinutes);
  }
}

export const passengerApi = new PassengerApi();
