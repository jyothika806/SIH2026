import {
  ActiveRideListing,
  clampOpenSeats,
  ConsolidationSuggestion,
  DEFAULT_DRIVER,
  DEFAULT_JOINER,
  DEFAULT_PASSENGER,
  DriverProfile,
  GeoLocation,
  PassengerProfile,
  RideState,
  TripRiskScore,
  VehicleMode,
  vehicleConfig,
} from '../types/commute';

const STORAGE_KEY = 'sih2026.commute.engine.v1';

export interface IncomingRideRequest {
  requestId: string;
  rideId: string;
  vehicleType: VehicleMode;
  pickup: GeoLocation;
  dropoff: GeoLocation;
  seatsRequired: number;
  fare: number;
  passenger: PassengerProfile;
  createdAt: string;
}

export interface MidRideJoin {
  requestId: string;
  rideId: string;
  requester: PassengerProfile;
  pickup: GeoLocation;
  dropoff: GeoLocation;
  estimatedDetourMinutes: number;
  additionalFare: number;
  votes: Record<string, 'accept' | 'reject'>;
  status: 'pending_consent' | 'approved' | 'rejected' | 'waypoint_accepted';
  createdAt: string;
}

export interface EngineState {
  driver: {
    id: string;
    online: boolean;
    vehicleType: VehicleMode;
    vacantSeats: number;
    location: GeoLocation;
    identityVerified: boolean;
    heading: number;
  };
  profile: DriverProfile;
  passenger: PassengerProfile;
  incomingRequests: IncomingRideRequest[];
  activeRide: RideState | null;
  midRideJoins: MidRideJoin[];
  lastSos?: { incidentId: string; at: string; source: 'passenger' | 'driver' };
}

function haversineKm(a: GeoLocation, b: GeoLocation): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h =
    sinLat * sinLat +
    Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * sinLng * sinLng;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

function seedState(): EngineState {
  return {
    driver: {
      id: DEFAULT_DRIVER.id,
      online: false,
      vehicleType: 'cab',
      vacantSeats: 3,
      location: { lat: 12.9716, lng: 77.5946, address: 'MG Road, Bengaluru' },
      identityVerified: false,
      heading: 92,
    },
    profile: { ...DEFAULT_DRIVER },
    passenger: { ...DEFAULT_PASSENGER },
    incomingRequests: [],
    activeRide: null,
    midRideJoins: [],
  };
}

function load(): EngineState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedState();
    return { ...seedState(), ...JSON.parse(raw) } as EngineState;
  } catch {
    return seedState();
  }
}

function save(state: EngineState): EngineState {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  window.dispatchEvent(new CustomEvent('sih2026-engine-updated'));
  return state;
}

export function subscribeEngine(onChange: () => void): () => void {
  const handler = () => onChange();
  window.addEventListener('sih2026-engine-updated', handler);
  window.addEventListener('storage', handler);
  return () => {
    window.removeEventListener('sih2026-engine-updated', handler);
    window.removeEventListener('storage', handler);
  };
}

export function getEngineState(): EngineState {
  return load();
}

export function calculateFare(mode: VehicleMode, distanceKm: number, durationMin: number): number {
  const v = vehicleConfig(mode);
  return Math.round((v.baseFare + v.perKmRate * distanceKm + durationMin) * 100) / 100;
}

export function computeRiskScore(
  pickup: GeoLocation,
  dropoff: GeoLocation,
  vehicleType: VehicleMode,
  hour = new Date().getHours()
): TripRiskScore {
  const night = hour < 6 || hour >= 20;
  const routeSafetyIndex = 78 + Math.round(((pickup.lat + dropoff.lat) % 1) * 12);
  const streetLightingIndex = night ? 48 : 86;
  const historicalIncidentFrequency = night ? 28 : 11;
  const timeOfDayRisk = night ? 62 : 18;
  const driverSafetyProfile = DEFAULT_DRIVER.safetyScore;
  const coPassengerSafetyRating = vehicleType === 'bike' ? 100 : 84;
  const composite =
    100 -
    Math.round(
      (100 - routeSafetyIndex) * 0.25 +
        timeOfDayRisk * 0.2 +
        (100 - streetLightingIndex) * 0.15 +
        historicalIncidentFrequency * 0.15 +
        (100 - driverSafetyProfile) * 0.15 +
        (100 - coPassengerSafetyRating) * 0.1
    );
  const scoreValue = Math.max(5, Math.min(95, composite));
  const score: TripRiskScore['score'] = scoreValue <= 30 ? 'low' : scoreValue <= 55 ? 'medium' : 'high';
  const recommendations: string[] = [];
  if (night) recommendations.push('Night travel detected — share trip and keep SOS armed.');
  else recommendations.push('Daylight corridor with strong street-lighting index.');
  if (driverSafetyProfile >= 85) recommendations.push('Driver safety profile is above fleet average.');
  if (vehicleType !== 'bike') recommendations.push('Pooled ride: co-passenger consent is required for mid-ride joins.');
  if (historicalIncidentFrequency > 20) recommendations.push('Historical incident frequency is elevated on this corridor.');
  return {
    score,
    scoreValue,
    factors: {
      routeSafetyIndex,
      timeOfDayRisk,
      streetLightingIndex,
      historicalIncidentFrequency,
      driverSafetyProfile,
      coPassengerSafetyRating,
    },
    recommendations,
  };
}

export function computeConsolidation(mode: VehicleMode): ConsolidationSuggestion[] {
  const suggestions: ConsolidationSuggestion[] = [];
  if (mode === 'bike') {
    suggestions.push({
      type: 'bike_to_auto',
      headline: '2 Bike requests nearby → 1 Auto',
      currentRequests: 2,
      suggestedVehicle: 'auto',
      savingsPercent: 30,
      originalFare: 50,
      estimatedFare: 35,
      driverBonus: 40,
    });
    suggestions.push({
      type: 'bike_to_cab',
      headline: '5 Bike requests overlapping → 1 Cab / Van',
      currentRequests: 5,
      suggestedVehicle: 'cab',
      savingsPercent: 38,
      originalFare: 125,
      estimatedFare: 78,
      driverBonus: 120,
    });
  }
  if (mode === 'auto' || mode === 'bike') {
    suggestions.push({
      type: 'auto_to_cab',
      headline: '1 Auto + 1 Bike cluster → 1 Cab',
      currentRequests: 2,
      suggestedVehicle: 'cab',
      savingsPercent: 22,
      originalFare: 90,
      estimatedFare: 70,
      driverBonus: 75,
    });
    suggestions.push({
      type: 'auto_to_van',
      headline: 'Group demand detected → upgrade to Van',
      currentRequests: 6,
      suggestedVehicle: 'van',
      savingsPercent: 28,
      originalFare: 210,
      estimatedFare: 151,
      driverBonus: 160,
    });
  }
  return suggestions;
}

export function setDriverStatus(online: boolean, vehicleType: VehicleMode): EngineState {
  const state = load();
  const cfg = vehicleConfig(vehicleType);
  state.driver.online = online;
  state.driver.vehicleType = vehicleType;
  state.profile.vehicleType = vehicleType;
  state.driver.vacantSeats = clampOpenSeats(vehicleType, cfg.maxOpenSeats);
  return save(state);
}

export function setVacantSeats(seats: number): EngineState {
  const state = load();
  state.driver.vacantSeats = clampOpenSeats(state.driver.vehicleType, seats);
  if (state.activeRide) {
    state.activeRide.openSeats = state.driver.vacantSeats;
    state.activeRide.occupiedSeats = Math.max(
      0,
      state.activeRide.capacity - state.driver.vacantSeats
    );
  }
  return save(state);
}

export function bookRide(input: {
  pickup: GeoLocation;
  dropoff: GeoLocation;
  vehicleType: VehicleMode;
  seatsRequired?: number;
  passengerId?: string;
}): { success: boolean; rideId: string; estimatedFare: number; estimatedDuration: number; message: string } {
  const state = load();
  const distance = Math.max(2.4, haversineKm(input.pickup, input.dropoff) || 8.5);
  const duration = Math.round(distance * 3.1);
  const fare = calculateFare(input.vehicleType, distance, duration);
  const rideId = `ride-${Date.now()}`;
  const request: IncomingRideRequest = {
    requestId: `req-${Date.now()}`,
    rideId,
    vehicleType: input.vehicleType,
    pickup: input.pickup,
    dropoff: input.dropoff,
    seatsRequired: input.seatsRequired ?? 1,
    fare,
    passenger: state.passenger,
    createdAt: new Date().toISOString(),
  };
  state.incomingRequests.unshift(request);
  assignRide(state, request);
  save(state);
  return {
    success: true,
    rideId,
    estimatedFare: fare,
    estimatedDuration: duration,
    message: 'Driver matched',
  };
}

function assignRide(state: EngineState, request: IncomingRideRequest) {
  const cfg = vehicleConfig(request.vehicleType);
  const open = clampOpenSeats(request.vehicleType, cfg.capacity - request.seatsRequired);
  const otp = String(Math.floor(1000 + Math.random() * 9000));
  state.driver.vehicleType = request.vehicleType;
  state.profile.vehicleType = request.vehicleType;
  state.driver.identityVerified = false;
  state.activeRide = {
    rideId: request.rideId,
    status: 'driver_assigned',
    vehicleType: request.vehicleType,
    seatsRequired: request.seatsRequired,
    occupiedSeats: request.seatsRequired,
    openSeats: open,
    capacity: cfg.capacity,
    fare: request.fare,
    extraFare: 0,
    distance: 8.5,
    duration: 25,
    eta: 8,
    pickup: request.pickup,
    dropoff: request.dropoff,
    passengerIds: [request.passenger.id],
    passengers: [request.passenger],
    driver: { ...state.profile, currentLocation: { ...state.driver.location } },
    identityVerified: false,
    otpLocked: true,
    otp,
    geofence: {
      active: true,
      radius: 220,
      corridorMeters: 100,
      driftMeters: 18,
      breached: false,
    },
    shareLink: `${window.location.origin}/passenger/track/${request.rideId}`,
    timestamp: new Date().toISOString(),
  };
  state.incomingRequests = state.incomingRequests.filter((r) => r.rideId !== request.rideId);
}

export function acceptIncomingRequest(requestId: string): EngineState {
  const state = load();
  const req = state.incomingRequests.find((r) => r.requestId === requestId);
  if (req) assignRide(state, req);
  return save(state);
}

export function listActivePoolRides(): ActiveRideListing[] {
  const state = load();
  if (!state.activeRide || !state.activeRide.driver) return [];
  if (state.activeRide.vehicleType === 'bike') return [];
  if (state.activeRide.openSeats < 1) return [];
  if (state.activeRide.status !== 'trip_started' && state.activeRide.status !== 'driver_assigned') {
    return [];
  }
  const ride = state.activeRide;
  return [
    {
      rideId: ride.rideId,
      vehicleType: ride.vehicleType,
      openSeats: ride.openSeats,
      occupiedSeats: ride.occupiedSeats,
      capacity: ride.capacity,
      pickup: ride.pickup,
      dropoff: ride.dropoff,
      extraFare: 48,
      detourMinutes: 2,
      driver: {
        name: ride.driver.name,
        age: ride.driver.age,
        gender: ride.driver.gender,
        rating: ride.driver.rating,
        vehicleNumber: ride.driver.vehicleNumber,
      },
      coPassengerCount: ride.passengers.length,
    },
  ];
}

export function requestMidRideJoin(rideId: string, pickup: GeoLocation, dropoff: GeoLocation) {
  const state = load();
  const requestId = `join-${Date.now()}`;
  const join: MidRideJoin = {
    requestId,
    rideId,
    requester: DEFAULT_JOINER,
    pickup,
    dropoff,
    estimatedDetourMinutes: 2,
    additionalFare: 48,
    votes: {},
    status: 'pending_consent',
    createdAt: new Date().toISOString(),
  };
  state.midRideJoins.unshift(join);
  save(state);
  return { success: true, requestId, message: 'Join request sent to co-passengers' };
}

export function pendingConsentForPassenger(passengerId: string): MidRideJoin | null {
  const state = load();
  return (
    state.midRideJoins.find(
      (j) => j.status === 'pending_consent' && !j.votes[passengerId]
    ) ?? null
  );
}

export function submitConsent(requestId: string, passengerId: string, consent: 'accept' | 'reject') {
  const state = load();
  const join = state.midRideJoins.find((j) => j.requestId === requestId);
  if (!join) return { success: false, consensusReached: false, message: 'Request not found' };
  join.votes[passengerId] = consent;
  const voters = state.activeRide?.passengerIds ?? [passengerId];
  const votes = voters.map((id) => join.votes[id]);
  const allVoted = votes.every(Boolean);
  const accepted = votes.filter((v) => v === 'accept').length;
  if (consent === 'reject') join.status = 'rejected';
  else if (allVoted && accepted >= Math.ceil(voters.length / 2)) join.status = 'approved';
  save(state);
  return {
    success: true,
    consensusReached: join.status === 'approved',
    approvals: accepted,
    required: voters.length,
    message: join.status === 'approved' ? 'Waypoint queued for driver' : 'Vote recorded',
  };
}

export function pendingWaypoint(): MidRideJoin | null {
  const state = load();
  return state.midRideJoins.find((j) => j.status === 'approved') ?? null;
}

export function acceptWaypoint(requestId: string) {
  const state = load();
  const join = state.midRideJoins.find((j) => j.requestId === requestId);
  if (!join || !state.activeRide) {
    return { success: false, message: 'No approved waypoint' };
  }
  join.status = 'waypoint_accepted';
  state.activeRide.passengers.push(join.requester);
  state.activeRide.passengerIds.push(join.requester.id);
  state.activeRide.occupiedSeats += 1;
  state.activeRide.openSeats = Math.max(0, state.activeRide.openSeats - 1);
  state.activeRide.extraFare += join.additionalFare;
  state.activeRide.fare += join.additionalFare;
  state.driver.vacantSeats = state.activeRide.openSeats;
  save(state);
  return {
    success: true,
    extraFare: join.additionalFare,
    detourMinutes: join.estimatedDetourMinutes,
    message: 'Waypoint added to route',
  };
}

export function verifyDriverIdentity(method: 'facial' | 'biometric' | 'pin') {
  const state = load();
  state.driver.identityVerified = true;
  if (state.activeRide) {
    state.activeRide.identityVerified = true;
    state.activeRide.otpLocked = false;
  }
  save(state);
  return {
    success: true,
    verified: true,
    method,
    otpUnlocked: state.activeRide?.otp ?? '4567',
    message: 'Identity verified. Trip start OTP unlocked.',
  };
}

export function startRide(otp: string) {
  const state = load();
  if (!state.activeRide) return { success: false, rideStarted: false, error: 'No active ride' };
  if (state.activeRide.otpLocked) {
    return { success: false, rideStarted: false, error: 'OTP locked until identity verification' };
  }
  if (otp !== state.activeRide.otp) {
    return { success: false, rideStarted: false, error: 'Invalid OTP' };
  }
  state.activeRide.status = 'trip_started';
  save(state);
  return { success: true, rideStarted: true, message: 'Trip started' };
}

export function completeRide() {
  const state = load();
  if (state.activeRide) {
    state.activeRide.status = 'completed';
  }
  const snapshot = state.activeRide;
  state.activeRide = null;
  state.driver.identityVerified = false;
  save(state);
  return { success: true, ride: snapshot };
}

export function streamDriverLocation(location: GeoLocation, driftMeters?: number) {
  const state = load();
  state.driver.location = location;
  if (state.activeRide?.driver) {
    state.activeRide.driver.currentLocation = location;
    const drift = driftMeters ?? state.activeRide.geofence.driftMeters;
    state.activeRide.geofence.driftMeters = drift;
    state.activeRide.geofence.breached = drift > 100;
    state.activeRide.timestamp = new Date().toISOString();
  }
  save(state);
  return { success: true, message: 'Location streamed', driftMeters: state.activeRide?.geofence.driftMeters ?? 0 };
}

export function streamPassengerStatus(rideId: string, location: GeoLocation) {
  const state = load();
  if (state.activeRide && state.activeRide.rideId === rideId) {
    state.activeRide.timestamp = new Date().toISOString();
  }
  save(state);
  return { success: true, rideId, location, message: 'Passenger status streamed' };
}

export function triggerSos(source: 'passenger' | 'driver') {
  const state = load();
  const incidentId = `sos-${Date.now()}`;
  state.lastSos = { incidentId, at: new Date().toISOString(), source };
  save(state);
  return {
    success: true,
    incidentId,
    emergencyContactsNotified: true,
    locationShared: true,
    securityCenterAlerted: true,
    message: 'SOS dispatched to tourism safety command',
  };
}

export function getRide(rideId: string): RideState | null {
  const state = load();
  if (state.activeRide) return state.activeRide;
  if (!rideId) return null;
  return null;
}

export function simulateDrift(breach: boolean) {
  const state = load();
  if (!state.activeRide) return state;
  state.activeRide.geofence.driftMeters = breach ? 165 : 22;
  state.activeRide.geofence.breached = breach;
  return save(state);
}

export function seedDemoConsent() {
  const state = load();
  if (!state.activeRide) return state;
  if (state.midRideJoins.some((j) => j.status === 'pending_consent')) return state;
  requestMidRideJoin(
    state.activeRide.rideId,
    { lat: 12.959, lng: 77.61, address: 'Trinity Circle' },
    state.activeRide.dropoff
  );
  return load();
}
