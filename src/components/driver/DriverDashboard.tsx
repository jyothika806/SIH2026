import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Car, Minus, Plus, Power, Users } from 'lucide-react';
import { driverApi } from '../../services/driverApi';
import { clampOpenSeats, VehicleMode, vehicleConfig } from '../../types/commute';
import { subscribeEngine } from '../../engine/commuteEngine';
import { DriverVerificationScreen } from './DriverVerificationScreen';
import { WaypointPickupModal } from './WaypointPickupModal';

export const DriverDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [tick, setTick] = useState(0);
  const [verify, setVerify] = useState(false);

  useEffect(() => subscribeEngine(() => setTick((t) => t + 1)), []);

  const snap = driverApi.snapshot();
  const cfg = vehicleConfig(snap.driver.vehicleType);
  const waypoint = driverApi.pendingWaypoint();

  const setMode = (vehicleType: VehicleMode) => {
    void driverApi.setStatus({ driverId: snap.driver.id, online: snap.driver.online, vehicleType });
  };

  const changeSeats = (delta: number) => {
    void driverApi.updateSeats({
      driverId: snap.driver.id,
      vacantSeats: clampOpenSeats(snap.driver.vehicleType, snap.driver.vacantSeats + delta),
    });
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xl font-bold">{snap.profile.name}</p>
            <p className="text-sm text-slate-500">
              {snap.profile.age} · {snap.profile.gender} · ★ {snap.profile.rating} · safety {snap.profile.safetyScore}
            </p>
          </div>
          <button
            onClick={() =>
              driverApi.setStatus({
                driverId: snap.driver.id,
                online: !snap.driver.online,
                vehicleType: snap.driver.vehicleType,
              })
            }
            className={`flex items-center gap-2 rounded-full px-4 py-2 font-semibold ${
              snap.driver.online ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
            }`}
          >
            <Power className="h-4 w-4" /> {snap.driver.online ? 'Online' : 'Offline'}
          </button>
        </div>
      </div>

      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="mb-3 flex items-center gap-2 font-semibold">
          <Car className="h-5 w-5 text-blue-600" /> Vehicle mode
        </h3>
        <select
          value={snap.driver.vehicleType}
          onChange={(e) => setMode(e.target.value as VehicleMode)}
          className="w-full rounded-lg border px-3 py-2"
        >
          <option value="bike">Bike Taxi · 1 passenger</option>
          <option value="auto">Auto · 3 seats (1–2 open)</option>
          <option value="cab">Cab · 4 seats (1–3 open)</option>
          <option value="van">Van · 7–8 seats</option>
        </select>

        {cfg.supportsPooling && (
          <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-50 p-4">
            <div>
              <p className="font-medium">Vacant seats</p>
              <p className="text-xs text-slate-500">
                Toggle {cfg.minOpenSeats}–{cfg.maxOpenSeats} during transit
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => changeSeats(-1)} className="rounded-full bg-white p-2 shadow">
                <Minus className="h-4 w-4" />
              </button>
              <span className="w-8 text-center text-xl font-bold">{snap.driver.vacantSeats}</span>
              <button onClick={() => changeSeats(1)} className="rounded-full bg-white p-2 shadow">
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm">
        Consolidation bonuses: Auto cluster +₹40 · Cab/Van group route +₹75–₹160
      </div>

      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="mb-3 flex items-center gap-2 font-semibold">
          <Users className="h-5 w-5" /> Incoming requests
        </h3>
        {snap.incomingRequests.length === 0 && <p className="text-sm text-slate-500">No queued requests</p>}
        {snap.incomingRequests.map((req) => (
          <div key={req.requestId} className="mb-3 rounded-lg border p-3 last:mb-0">
            <p className="font-medium">
              {req.passenger.name} · {req.vehicleType} · ₹{req.fare}
            </p>
            <p className="text-xs text-slate-500">
              {req.pickup.address} → {req.dropoff.address}
            </p>
            <button
              onClick={() => driverApi.acceptIncoming(req.requestId)}
              className="mt-2 rounded-lg bg-blue-600 px-3 py-1 text-sm text-white"
            >
              Accept
            </button>
          </div>
        ))}
      </div>

      {snap.activeRide && (
        <button
          onClick={() => navigate('/driver/active-ride')}
          className="w-full rounded-xl bg-indigo-600 py-4 font-semibold text-white"
        >
          Open active ride {snap.activeRide.rideId.slice(-6)}
        </button>
      )}

      {snap.activeRide && !snap.activeRide.identityVerified && (
        <button onClick={() => setVerify(true)} className="w-full rounded-xl bg-slate-800 py-3 text-white">
          Verify identity to unlock OTP
        </button>
      )}

      {verify && (
        <DriverVerificationScreen
          driverId="driver-001"
          onCancel={() => setVerify(false)}
          onVerificationSuccess={() => setVerify(false)}
        />
      )}
      {waypoint && snap.activeRide && (
        <WaypointPickupModal
          join={waypoint}
          occupantCount={snap.activeRide.passengers.length}
          onResolved={() => setTick((t) => t + 1)}
        />
      )}
    </div>
  );
};
