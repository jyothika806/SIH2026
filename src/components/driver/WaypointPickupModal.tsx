import React, { useState } from 'react';
import { Check, Clock, DollarSign, MapPin, Users, X } from 'lucide-react';
import { driverApi } from '../../services/driverApi';
import { MidRideJoin } from '../../engine/commuteEngine';

interface WaypointPickupModalProps {
  join: MidRideJoin;
  occupantCount: number;
  onResolved: () => void;
}

export const WaypointPickupModal: React.FC<WaypointPickupModalProps> = ({ join, occupantCount, onResolved }) => {
  const [busy, setBusy] = useState(false);
  const approvals = Object.values(join.votes).filter((v) => v === 'accept').length;

  const accept = async () => {
    setBusy(true);
    await driverApi.acceptWaypoint({ requestId: join.requestId, rideId: join.rideId, driverId: 'driver-001' });
    setBusy(false);
    onResolved();
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-bold">En-route pickup</h3>
          <button onClick={onResolved}>
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mb-3 flex items-center gap-2 text-sm text-emerald-700">
          <Users className="h-4 w-4" /> Approved {approvals}/{Math.max(approvals, occupantCount)} co-passengers
        </p>
        <p className="font-semibold">{join.requester.name}</p>
        <p className="mb-3 text-sm capitalize text-slate-600">
          {join.requester.age} · {join.requester.gender} · ★ {join.requester.rating}
        </p>
        <p className="flex items-center gap-2 text-sm">
          <MapPin className="h-4 w-4 text-emerald-600" /> {join.pickup.address}
        </p>
        <p className="mt-2 flex items-center gap-2 text-sm">
          <DollarSign className="h-4 w-4" /> Extra earnings ₹{join.additionalFare}
        </p>
        <p className="mt-1 flex items-center gap-2 text-sm">
          <Clock className="h-4 w-4" /> Detour +{join.estimatedDetourMinutes} mins
        </p>
        <button
          disabled={busy}
          onClick={accept}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 font-semibold text-white"
        >
          <Check className="h-5 w-5" /> Confirm waypoint pickup
        </button>
      </div>
    </div>
  );
};
