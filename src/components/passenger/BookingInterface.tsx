import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2, MapPin, Navigation, TrendingDown, Users } from 'lucide-react';
import { passengerApi } from '../../services/passengerApi';
import { TripRiskIndicator } from './TripRiskIndicator';
import {
  ActiveRideListing,
  ConsolidationSuggestion,
  GeoLocation,
  VehicleMode,
} from '../../types/commute';

interface BookingInterfaceProps {
  onRideBooked?: (rideId: string) => void;
}

export const BookingInterface: React.FC<BookingInterfaceProps> = ({ onRideBooked }) => {
  const [pickup, setPickup] = useState<GeoLocation>({
    lat: 12.9716,
    lng: 77.5946,
    address: 'MG Road, Bengaluru',
  });
  const [dropoff, setDropoff] = useState<GeoLocation>({
    lat: 12.9352,
    lng: 77.6245,
    address: 'Indiranagar, Bengaluru',
  });
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleMode>('cab');
  const [seatsRequired, setSeatsRequired] = useState(1);
  const [distance] = useState(8.5);
  const [duration] = useState(25);
  const [fare, setFare] = useState(0);
  const [booking, setBooking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<ConsolidationSuggestion[]>([]);
  const [activeRides, setActiveRides] = useState<ActiveRideListing[]>([]);
  const [joining, setJoining] = useState<string | null>(null);

  const vehicleTypes = passengerApi.getVehicleTypes();
  const selected = vehicleTypes.find((v) => v.id === selectedVehicle);

  useEffect(() => {
    setFare(passengerApi.calculateFare(selectedVehicle, distance, duration));
    void passengerApi.getConsolidationSuggestion(selectedVehicle).then(setSuggestions);
    void passengerApi.listActiveRides().then(setActiveRides);
  }, [selectedVehicle, distance, duration]);

  useEffect(() => {
    if (selected && seatsRequired > selected.capacity) setSeatsRequired(selected.capacity);
  }, [selected, seatsRequired]);

  const book = async () => {
    setBooking(true);
    setError(null);
    try {
      const response = await passengerApi.bookRide({
        pickup,
        dropoff,
        vehicleType: selectedVehicle,
        seatsRequired,
        passengerId: 'passenger-001',
      });
      if (response.success && response.rideId) onRideBooked?.(response.rideId);
      else setError(response.error || 'Booking failed');
    } catch {
      setError('Unable to book ride');
    } finally {
      setBooking(false);
    }
  };

  const joinActive = async (ride: ActiveRideListing) => {
    setJoining(ride.rideId);
    try {
      await passengerApi.requestMidRideJoin({ rideId: ride.rideId, pickup, dropoff });
      onRideBooked?.(ride.rideId);
    } catch {
      setError('Join request failed');
    } finally {
      setJoining(null);
    }
  };

  return (
    <div className="mx-auto w-full rounded-2xl bg-white p-6 shadow-xl">
      <h2 className="mb-6 flex items-center gap-2 text-2xl font-bold text-slate-800">
        <Navigation className="h-6 w-6 text-blue-600" />
        Book a safe ride
      </h2>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-red-700">
          <AlertTriangle className="h-5 w-5" /> {error}
        </div>
      )}

      <div className="mb-6 space-y-4">
        <label className="block text-sm font-medium text-slate-700">Pickup</label>
        <div className="relative">
          <MapPin className="absolute left-3 top-3 h-5 w-5 text-emerald-600" />
          <input
            value={pickup.address}
            onChange={(e) => setPickup({ ...pickup, address: e.target.value })}
            className="w-full rounded-lg border border-slate-300 py-3 pl-10 pr-4"
          />
        </div>
        <label className="block text-sm font-medium text-slate-700">Drop-off</label>
        <div className="relative">
          <MapPin className="absolute left-3 top-3 h-5 w-5 text-red-600" />
          <input
            value={dropoff.address}
            onChange={(e) => setDropoff({ ...dropoff, address: e.target.value })}
            className="w-full rounded-lg border border-slate-300 py-3 pl-10 pr-4"
          />
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {vehicleTypes.map((vehicle) => (
          <button
            key={vehicle.id}
            onClick={() => setSelectedVehicle(vehicle.id)}
            className={`rounded-xl border-2 p-4 text-left ${
              selectedVehicle === vehicle.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200'
            }`}
          >
            <div className="mb-1 text-2xl">{vehicle.icon}</div>
            <p className="font-semibold">{vehicle.name}</p>
            <p className="text-xs text-slate-500">
              {vehicle.capacity} seats · {vehicle.supportsPooling ? 'pool' : 'solo'}
            </p>
          </button>
        ))}
      </div>

      {selected && selected.capacity > 1 && (
        <div className="mb-6">
          <label className="mb-2 block text-sm font-medium">Seats needed (max {selected.capacity})</label>
          <input
            type="range"
            min={1}
            max={selected.capacity}
            value={seatsRequired}
            onChange={(e) => setSeatsRequired(Number(e.target.value))}
            className="w-full"
          />
          <p className="mt-1 text-sm text-slate-600">{seatsRequired} seat(s)</p>
        </div>
      )}

      {activeRides.length > 0 && (
        <div className="mb-6 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-indigo-900">
            <Users className="h-4 w-4" /> Existing active rides on this corridor
          </h3>
          {activeRides.map((ride) => (
            <div key={ride.rideId} className="mb-3 rounded-lg bg-white p-3 last:mb-0">
              <p className="font-medium capitalize">
                {ride.vehicleType} · {ride.openSeats} open / {ride.capacity}
              </p>
              <p className="text-sm text-slate-600">
                {ride.driver.name}, {ride.driver.age}, {ride.driver.gender} · ★ {ride.driver.rating} ·{' '}
                {ride.coPassengerCount} co-passenger(s)
              </p>
              <p className="text-xs text-slate-500">Detour +{ride.detourMinutes} min · extra fare ₹{ride.extraFare}</p>
              <button
                disabled={joining === ride.rideId}
                onClick={() => joinActive(ride)}
                className="mt-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white"
              >
                {joining === ride.rideId ? 'Requesting…' : 'Request to join'}
              </button>
            </div>
          ))}
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="mb-6 space-y-3">
          {suggestions.map((s) => (
            <button
              key={s.type}
              onClick={() => setSelectedVehicle(s.suggestedVehicle)}
              className="flex w-full items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-left"
            >
              <TrendingDown className="mt-0.5 h-5 w-5 text-emerald-700" />
              <div>
                <p className="font-semibold text-emerald-900">{s.headline}</p>
                <p className="text-sm text-emerald-800">
                  Save {s.savingsPercent}% (₹{s.originalFare} → ₹{s.estimatedFare}) · driver bonus ₹{s.driverBonus}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="mb-6">
        <TripRiskIndicator pickup={pickup} dropoff={dropoff} vehicleType={selectedVehicle} />
      </div>

      <div className="mb-6 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 p-4">
        <p className="text-sm text-slate-600">Estimated fare</p>
        <p className="text-2xl font-bold">₹{fare.toFixed(0)}</p>
        <p className="text-xs text-slate-500">
          {distance} km · {duration} min
        </p>
      </div>

      <button
        onClick={book}
        disabled={booking}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 py-4 font-semibold text-white disabled:opacity-60"
      >
        {booking ? <Loader2 className="h-5 w-5 animate-spin" /> : <Navigation className="h-5 w-5" />}
        Request {selected?.name}
      </button>
    </div>
  );
};
