import React, { useEffect, useState } from 'react';
import { Lock, MapPin, Navigation, Shield, ShieldAlert, Star, Unlock, Volume2, VolumeX } from 'lucide-react';
import { passengerApi } from '../../services/passengerApi';
import { RideState } from '../../types/commute';
import { seedDemoConsent, simulateDrift, subscribeEngine } from '../../engine/commuteEngine';
import { MidRideConsentModal } from './MidRideConsentModal';
import { useSiren } from './SafetyFeatures';

interface LiveRideTrackingProps {
  rideId: string;
  onRideComplete?: () => void;
}

export const LiveRideTracking: React.FC<LiveRideTrackingProps> = ({ rideId, onRideComplete }) => {
  const [ride, setRide] = useState<RideState | null>(null);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);

  const consent = passengerApi.getPendingConsent();
  useSiren(Boolean(ride?.geofence.breached), muted);

  const refresh = async () => {
    try {
      const status = await passengerApi.getRideStatus(rideId);
      setRide(status);
      await passengerApi.streamStatus(rideId, status.driver?.currentLocation || status.pickup);
      if (status.status === 'completed') onRideComplete?.();
    } catch {
      setError('Unable to load ride');
    }
  };

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 4000);
    const unsub = subscribeEngine(() => void refresh());
    return () => {
      window.clearInterval(interval);
      unsub();
    };
  }, [rideId]);

  if (error) return <div className="rounded-2xl bg-white p-8 text-red-600 shadow-xl">{error}</div>;
  if (!ride) return <div className="rounded-2xl bg-white p-8 shadow-xl">Matching driver…</div>;

  const progress = ride.status === 'trip_started' ? 62 : ride.status === 'arrived' ? 35 : 18;

  return (
    <div className="rounded-2xl bg-white p-6 shadow-xl">
      <div className="mb-5 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-2xl font-bold">
          <Navigation className="h-6 w-6 text-blue-600" /> Live tracking
        </h2>
        <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold capitalize text-blue-800">
          {ride.status.replace('_', ' ')}
        </span>
      </div>

      <div className="relative mb-6 h-64 overflow-hidden rounded-xl bg-slate-900">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.18),transparent_62%)]" />
        <div className="absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/40" />
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cyan-300/70"
          style={{ width: `${Math.min(220, ride.geofence.radius / 2)}px`, height: `${Math.min(220, ride.geofence.radius / 2)}px` }}
        />
        <div
          className={`absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full ${
            ride.geofence.breached ? 'bg-red-500' : 'bg-emerald-400'
          }`}
          style={{ left: `${48 + Math.min(30, ride.geofence.driftMeters / 6)}%`, top: '46%' }}
        />
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-xs text-cyan-100">
          <span>Radar · r={ride.geofence.radius}m</span>
          <span>Drift {ride.geofence.driftMeters}m</span>
        </div>
        <div className="absolute left-0 top-10 h-1 bg-cyan-400/80" style={{ width: `${progress}%` }} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-emerald-50 p-4">
          <p className="text-xs text-slate-500">ETA</p>
          <p className="text-2xl font-bold">{ride.eta} min</p>
        </div>
        <div className={`rounded-xl p-4 ${ride.geofence.breached ? 'bg-red-50' : 'bg-slate-50'}`}>
          <p className="flex items-center gap-1 text-xs text-slate-500">
            {ride.geofence.breached ? <ShieldAlert className="h-4 w-4 text-red-600" /> : <Shield className="h-4 w-4 text-emerald-600" />}
            Geofence
          </p>
          <p className="font-semibold">{ride.geofence.breached ? 'Corridor breach >100m' : 'Inside corridor'}</p>
        </div>
      </div>

      {ride.geofence.breached && (
        <div className="mb-4 flex items-center justify-between rounded-xl border-2 border-red-200 bg-red-50 p-3">
          <p className="font-semibold text-red-800">Siren: vehicle left planned corridor</p>
          <button onClick={() => setMuted((m) => !m)}>{muted ? <VolumeX /> : <Volume2 className="animate-pulse text-red-600" />}</button>
        </div>
      )}

      {ride.driver && (
        <div className="mb-4 rounded-xl bg-slate-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">{ride.driver.name}</p>
              <p className="text-sm capitalize text-slate-600">
                {ride.driver.age} yrs · {ride.driver.gender} · {ride.driver.vehicleNumber}
              </p>
              <p className="flex items-center gap-1 text-sm">
                <Star className="h-4 w-4 fill-amber-400 text-amber-400" /> {ride.driver.rating}
              </p>
            </div>
            <p className="text-sm text-slate-500">
              {ride.occupiedSeats}/{ride.capacity} seated · {ride.openSeats} open
            </p>
          </div>
        </div>
      )}

      <div className="mb-4 space-y-2 text-sm">
        <p className="flex gap-2">
          <MapPin className="h-4 w-4 text-emerald-600" /> {ride.pickup.address}
        </p>
        <p className="flex gap-2">
          <MapPin className="h-4 w-4 text-red-600" /> {ride.dropoff.address}
        </p>
      </div>

      <div className={`mb-4 rounded-xl p-4 ${ride.otpLocked ? 'bg-slate-100' : 'bg-amber-50'}`}>
        <p className="mb-2 flex items-center gap-2 font-semibold">
          {ride.otpLocked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4 text-emerald-700" />}
          Trip start OTP
        </p>
        <p className="text-center text-4xl font-bold tracking-[0.4em]">
          {ride.otpLocked ? '••••' : ride.otp}
        </p>
        {ride.otpLocked ? (
          <button
            disabled={verifying}
            onClick={async () => {
              setVerifying(true);
              await fetch('/api/v1/driver/verify-identity', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ driverId: 'driver-001', verificationMethod: 'facial' }),
              }).catch(() => undefined);
              const { driverApi } = await import('../../services/driverApi');
              await driverApi.verifyIdentity({ driverId: 'driver-001', verificationMethod: 'facial' });
              setVerifying(false);
              void refresh();
            }}
            className="mt-3 w-full rounded-lg bg-blue-600 py-2 text-white"
          >
            {verifying ? 'Requesting scan…' : 'Verify driver identity'}
          </button>
        ) : (
          <p className="mt-2 text-center text-xs text-emerald-700">Identity verified — OTP unlocked for passenger and driver</p>
        )}
      </div>

      <div className="flex gap-2">
        <button onClick={() => simulateDrift(true)} className="flex-1 rounded-lg bg-red-50 py-2 text-sm text-red-700">
          Simulate 165m drift
        </button>
        <button onClick={() => simulateDrift(false)} className="flex-1 rounded-lg bg-emerald-50 py-2 text-sm text-emerald-700">
          Restore corridor
        </button>
        <button onClick={() => seedDemoConsent()} className="flex-1 rounded-lg bg-indigo-50 py-2 text-sm text-indigo-700">
          Demo join request
        </button>
      </div>

      {consent && (
        <MidRideConsentModal
          request={{
            requestId: consent.requestId,
            rideId: consent.rideId,
            requester: consent.requester,
            pickup: consent.pickup,
            dropoff: consent.dropoff,
            estimatedDetourMinutes: consent.estimatedDetourMinutes,
            additionalFare: consent.additionalFare,
            currentPassengers: ride.passengers,
            timeoutSeconds: 30,
          }}
          onClose={() => void refresh()}
        />
      )}
    </div>
  );
};
