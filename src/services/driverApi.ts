import { DriverProfile, GeoLocation, VehicleMode } from '../types/commute';
import {
  acceptIncomingRequest,
  acceptWaypoint,
  completeRide,
  getEngineState,
  pendingWaypoint,
  setDriverStatus,
  setVacantSeats,
  streamDriverLocation,
  triggerSos,
} from '../engine/commuteEngine';
import { authenticatedFetch } from './authenticatedFetch';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export type { VehicleMode, DriverProfile, GeoLocation as Location };

async function postGateway(endpoint: string, body: unknown) {
  try {
    await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    /* FastAPI optional */
  }
}

async function requestGateway(endpoint: string, body: unknown) {
  const response = await authenticatedFetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Backend verification is unavailable');
  }
  return payload;
}

class DriverApi {
  async setStatus(payload: { driverId: string; online: boolean; vehicleType: VehicleMode }) {
    const state = setDriverStatus(payload.online, payload.vehicleType);
    void postGateway('/api/v1/driver/status', payload);
    return {
      success: true,
      online: state.driver.online,
      vehicleType: state.driver.vehicleType,
      vacantSeats: state.driver.vacantSeats,
    };
  }

  async updateSeats(payload: { driverId: string; vacantSeats: number }) {
    const state = setVacantSeats(payload.vacantSeats);
    void postGateway('/api/v1/driver/seats', payload);
    return { success: true, vacantSeats: state.driver.vacantSeats };
  }

  async verifyIdentity(payload: {
    rideId: string;
    driverId: string;
    verificationMethod: 'facial' | 'biometric' | 'pin';
    facialData?: string;
    biometricData?: string;
    pin?: string;
  }) {
    try {
      await requestGateway('/api/v1/liveness/request-verification', {
        ride_id: Number(payload.rideId),
      });
      return {
        success: false,
        verified: false,
        error: 'The backend did not confirm driver identity; OTP remains locked.',
      };
    } catch (error) {
      return {
        success: false,
        verified: false,
        error: error instanceof Error ? error.message : 'Driver verification failed',
      };
    }
  }

  async acceptWaypoint(payload: { requestId: string; rideId: string; driverId: string }) {
    const local = acceptWaypoint(payload.requestId);
    void postGateway('/api/v1/driver/accept-waypoint', payload);
    return local;
  }

  async streamLocation(payload: {
    driverId: string;
    rideId?: string;
    location: GeoLocation;
    heading?: number;
    speed?: number;
    driftMeters?: number;
  }) {
    const local = streamDriverLocation(payload.location, payload.driftMeters);
    void postGateway('/api/v1/driver/location', payload);
    return local;
  }

  async startRide(payload: { rideId: string; driverId: string; otp: string; currentLocation: GeoLocation }) {
    try {
      const result = await requestGateway(
        `/api/v1/rides/${encodeURIComponent(payload.rideId)}/start`,
        { otp: payload.otp },
      );
      return {
        success: result.status === 'in_progress',
        rideStarted: result.status === 'in_progress',
        message: result.status === 'in_progress' ? 'Trip started' : undefined,
        error: result.status === 'in_progress' ? undefined : 'Backend did not start the ride',
      };
    } catch (error) {
      return {
        success: false,
        rideStarted: false,
        error: error instanceof Error ? error.message : 'Ride start failed',
      };
    }
  }

  async completeTrip(rideId: string) {
    const local = completeRide();
    void postGateway('/api/v1/driver/complete', { rideId });
    return local;
  }

  async triggerSOS(location: GeoLocation) {
    const local = triggerSos('driver');
    void postGateway('/api/v1/driver/sos', { location });
    return local;
  }

  async acceptIncoming(requestId: string) {
    acceptIncomingRequest(requestId);
    void postGateway('/api/v1/driver/accept-request', { requestId });
    return { success: true };
  }

  getDriverProfile(): DriverProfile {
    return getEngineState().profile;
  }

  snapshot() {
    return getEngineState();
  }

  pendingWaypoint() {
    return pendingWaypoint();
  }
}

export const driverApi = new DriverApi();
