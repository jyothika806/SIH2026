import { DriverProfile, GeoLocation, VehicleMode } from '../types/commute';
import {
  acceptIncomingRequest,
  acceptWaypoint,
  completeRide,
  getEngineState,
  pendingWaypoint,
  setDriverStatus,
  setVacantSeats,
  startRide,
  streamDriverLocation,
  triggerSos,
  verifyDriverIdentity,
} from '../engine/commuteEngine';

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
    driverId: string;
    verificationMethod: 'facial' | 'biometric' | 'pin';
    facialData?: string;
    biometricData?: string;
    pin?: string;
  }) {
    const local = verifyDriverIdentity(payload.verificationMethod);
    void postGateway('/api/v1/driver/verify-identity', payload);
    return local;
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
    const local = startRide(payload.otp);
    void postGateway('/api/v1/driver/start-ride', payload);
    return local;
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
