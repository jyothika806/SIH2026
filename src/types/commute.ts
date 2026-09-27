export type VehicleMode = 'bike' | 'auto' | 'cab' | 'van';
export type Gender = 'male' | 'female' | 'other';
export type RiskLevel = 'low' | 'medium' | 'high';
export type RideStatusCode =
  | 'requested'
  | 'driver_assigned'
  | 'arrived'
  | 'trip_started'
  | 'trip_ended'
  | 'completed'
  | 'cancelled';

export interface GeoLocation {
  lat: number;
  lng: number;
  address?: string;
}

export interface VehicleType {
  id: VehicleMode;
  name: string;
  icon: string;
  baseFare: number;
  perKmRate: number;
  capacity: number;
  minOpenSeats: number;
  maxOpenSeats: number;
  supportsPooling: boolean;
}

export const VEHICLE_TYPES: VehicleType[] = [
  {
    id: 'bike',
    name: 'Bike Taxi',
    icon: '🏍️',
    baseFare: 15,
    perKmRate: 5,
    capacity: 1,
    minOpenSeats: 0,
    maxOpenSeats: 0,
    supportsPooling: false,
  },
  {
    id: 'auto',
    name: 'Auto Rickshaw',
    icon: '🛺',
    baseFare: 25,
    perKmRate: 8,
    capacity: 3,
    minOpenSeats: 1,
    maxOpenSeats: 2,
    supportsPooling: true,
  },
  {
    id: 'cab',
    name: 'Cab',
    icon: '🚕',
    baseFare: 45,
    perKmRate: 12,
    capacity: 4,
    minOpenSeats: 1,
    maxOpenSeats: 3,
    supportsPooling: true,
  },
  {
    id: 'van',
    name: 'Van',
    icon: '🚐',
    baseFare: 80,
    perKmRate: 15,
    capacity: 8,
    minOpenSeats: 1,
    maxOpenSeats: 7,
    supportsPooling: true,
  },
];

export interface PassengerProfile {
  id: string;
  name: string;
  age: number;
  gender: Gender;
  safetyRating: number;
  rating: number;
  photoUrl?: string;
}

export interface DriverProfile {
  id: string;
  name: string;
  age: number;
  gender: Gender;
  phone: string;
  vehicleNumber: string;
  vehicleModel: string;
  vehicleColor: string;
  vehicleType: VehicleMode;
  rating: number;
  totalTrips: number;
  safetyScore: number;
  suddenBrakingEvents: number;
  speedViolations: number;
  photoUrl?: string;
}

export interface TripRiskScore {
  score: RiskLevel;
  scoreValue: number;
  factors: {
    routeSafetyIndex: number;
    timeOfDayRisk: number;
    streetLightingIndex: number;
    historicalIncidentFrequency: number;
    driverSafetyProfile: number;
    coPassengerSafetyRating: number;
  };
  recommendations: string[];
}

export interface ConsolidationSuggestion {
  type: 'bike_to_auto' | 'bike_to_cab' | 'bike_to_van' | 'auto_to_cab' | 'auto_to_van';
  headline: string;
  currentRequests: number;
  suggestedVehicle: VehicleMode;
  savingsPercent: number;
  estimatedFare: number;
  originalFare: number;
  driverBonus: number;
}

export interface ActiveRideListing {
  rideId: string;
  vehicleType: VehicleMode;
  openSeats: number;
  occupiedSeats: number;
  capacity: number;
  pickup: GeoLocation;
  dropoff: GeoLocation;
  extraFare: number;
  detourMinutes: number;
  driver: {
    name: string;
    age: number;
    gender: Gender;
    rating: number;
    vehicleNumber: string;
  };
  coPassengerCount: number;
}

export interface RideState {
  rideId: string;
  status: RideStatusCode;
  vehicleType: VehicleMode;
  seatsRequired: number;
  occupiedSeats: number;
  openSeats: number;
  capacity: number;
  fare: number;
  extraFare: number;
  distance: number;
  duration: number;
  eta: number;
  pickup: GeoLocation;
  dropoff: GeoLocation;
  passengerIds: string[];
  passengers: PassengerProfile[];
  driver?: DriverProfile & { currentLocation: GeoLocation };
  identityVerified: boolean;
  otpLocked: boolean;
  otp?: string;
  geofence: {
    active: boolean;
    radius: number;
    corridorMeters: number;
    driftMeters: number;
    breached: boolean;
  };
  shareLink: string;
  timestamp: string;
}

export const DEFAULT_PASSENGER: PassengerProfile = {
  id: 'passenger-001',
  name: 'Priya Sharma',
  age: 26,
  gender: 'female',
  safetyRating: 91,
  rating: 4.7,
};

export const DEFAULT_JOINER: PassengerProfile = {
  id: 'passenger-002',
  name: 'Arjun Nair',
  age: 29,
  gender: 'male',
  safetyRating: 88,
  rating: 4.6,
};

export const DEFAULT_DRIVER: DriverProfile = {
  id: 'driver-001',
  name: 'Rajesh Kumar',
  age: 34,
  gender: 'male',
  phone: '+91 98765 43210',
  vehicleNumber: 'KA 01 AB 1234',
  vehicleModel: 'Maruti Suzuki Swift',
  vehicleColor: 'White',
  vehicleType: 'cab',
  rating: 4.8,
  totalTrips: 1250,
  safetyScore: 92,
  suddenBrakingEvents: 2,
  speedViolations: 1,
};

export function vehicleConfig(mode: VehicleMode): VehicleType {
  return VEHICLE_TYPES.find((v) => v.id === mode) ?? VEHICLE_TYPES[2];
}

export function clampOpenSeats(mode: VehicleMode, seats: number): number {
  const cfg = vehicleConfig(mode);
  if (!cfg.supportsPooling) return 0;
  return Math.min(cfg.maxOpenSeats, Math.max(cfg.minOpenSeats, seats));
}
