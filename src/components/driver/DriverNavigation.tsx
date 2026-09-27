import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, MapPin, Navigation, ShieldAlert } from 'lucide-react';
import { driverApi } from '../../services/driverApi';
import { subscribeEngine } from '../../engine/commuteEngine';
import { SafetyFeatures, useSiren } from '../passenger/SafetyFeatures';
import { DriverVerificationScreen } from './DriverVerificationScreen';
import { WaypointPickupModal } from './WaypointPickupModal';

export const DriverNavigation: React.FC = () => {
  const navigate = useNavigate();
  const [otp, setOtp] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [verify, setVerify] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => subscribeEngine(() => setTick((t) => t + 1)), []);

  const snap = driverApi.snapshot();
  const ride = snap.activeRide;
  const waypoint = driverApi.pendingWaypoint();
  useSiren(Boolean(ride?.geofence.breached), false);

  useEffect(() => {
    if (!ride) return;
    const id = window.setInterval(() => {
      const drift = ride.geofence.breached ? 165 : 20 + (tick % 8);
      void driverApi.streamLocation({
        driverId: 'driver-001',
        rideId: ride.rideId,
        location: {
          lat: 12.9716 + (tick % 10) * 0.0004,
          lng: 77.5946 + (tick % 10) * 0.0003,
          address: 'Live GPS',
        },
        driftMeters: drift,
      });
    }, 5000);
    return () => window.clearInterval(id);
  }, [ride?.rideId, tick]);

  if (!ride) {
    return (
      <div className="rounded-2xl bg-white p-8 text-center shadow-xl">
        <p className="mb-4">No active ride</p>
        <button onClick={() => navigate('/driver')} className="text-blue-600">
          Back to dashboard
        </button>
      </div>
    );
  }

  const steps = [
    'Head southeast on MG Road',
    'Continue onto Trinity Circle',
    'Turn right toward Indiranagar 100 Feet Rd',
    `Arrive ${ride.dropoff.address}`,
  ];

  return (
    <div className="space-y-4">
      {ride.geofence.breached && (
        <div className="flex items-center gap-2 rounded-xl border-2 border-red-300 bg-red-50 p-4 font-semibold text-red-800">
          <ShieldAlert className="h-5 w-5" /> Geofence drift {ride.geofence.driftMeters}m — siren armed
        </div>
      )}

      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 flex items-center gap-2 text-xl font-bold">
          <Navigation className="h-5 w-5 text-blue-600" /> Turn-by-turn
        </h2>
        <ol className="space-y-2 text-sm">
          {steps.map((step, i) => (
            <li key={step} className="flex gap-3">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs font-bold">{i + 1}</span>
              {step}
            </li>
          ))}
        </ol>
        <p className="mt-4 flex items-center gap-2 text-sm text-slate-600">
          <MapPin className="h-4 w-4" /> Occupied {ride.occupiedSeats}/{ride.capacity} · vacant {ride.openSeats}
        </p>
      </div>

      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <p className="mb-2 text-sm font-medium">Trip start OTP {ride.otpLocked ? '(locked)' : ''}</p>
        {ride.otpLocked ? (
          <button onClick={() => setVerify(true)} className="w-full rounded-xl bg-blue-600 py-3 text-white">
            Open identity verification
          </button>
        ) : (
          <>
            <p className="mb-2 text-center text-3xl font-bold tracking-[0.4em]">{ride.otp}</p>
            <input
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              maxLength={4}
              placeholder="Enter OTP from passenger"
              className="mb-3 w-full rounded-lg border px-3 py-2 text-center tracking-[0.4em]"
            />
            <button
              onClick={async () => {
                const res = await driverApi.startRide({
                  rideId: ride.rideId,
                  driverId: 'driver-001',
                  otp,
                  currentLocation: snap.driver.location,
                });
                setMessage(res.message || res.error || null);
              }}
              className="w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white"
            >
              Start trip
            </button>
          </>
        )}
        {message && <p className="mt-2 text-sm text-slate-600">{message}</p>}
      </div>

      <button
        onClick={async () => {
          await driverApi.completeTrip(ride.rideId);
          navigate('/driver');
        }}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-800 py-4 font-semibold text-white"
      >
        <CheckCircle className="h-5 w-5" /> Complete trip
      </button>

      <SafetyFeatures rideId={ride.rideId} currentLocation={snap.driver.location} />

      {verify && (
        <DriverVerificationScreen
          driverId="driver-001"
          onCancel={() => setVerify(false)}
          onVerificationSuccess={() => setVerify(false)}
        />
      )}
      {waypoint && (
        <WaypointPickupModal
          join={waypoint}
          occupantCount={ride.passengers.length}
          onResolved={() => setTick((t) => t + 1)}
        />
      )}
    </div>
  );
};
