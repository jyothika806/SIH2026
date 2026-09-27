import React, { useEffect, useState } from 'react';
import { Check, Clock, DollarSign, MapPin, Users, X } from 'lucide-react';
import { passengerApi } from '../../services/passengerApi';
import { GeoLocation, PassengerProfile } from '../../types/commute';

export interface MidRideJoinRequestData {
  requestId: string;
  rideId: string;
  requester: PassengerProfile;
  pickup: GeoLocation;
  dropoff: GeoLocation;
  estimatedDetourMinutes: number;
  additionalFare: number;
  currentPassengers: PassengerProfile[];
  timeoutSeconds: number;
}

interface MidRideConsentModalProps {
  request: MidRideJoinRequestData;
  passengerId?: string;
  onDecision?: (accepted: boolean, consensusReached: boolean) => void;
  onClose?: () => void;
}

export const MidRideConsentModal: React.FC<MidRideConsentModalProps> = ({
  request,
  passengerId = 'passenger-001',
  onDecision,
  onClose,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState(request.timeoutSeconds);

  useEffect(() => {
    if (timeLeft <= 0) {
      void handleDecision(false);
      return;
    }
    const timer = window.setInterval(() => setTimeLeft((t) => t - 1), 1000);
    return () => window.clearInterval(timer);
  }, [timeLeft]);

  const handleDecision = async (accepted: boolean) => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await passengerApi.submitMidRideConsent({
        requestId: request.requestId,
        rideId: request.rideId,
        consent: accepted ? 'accept' : 'reject',
        passengerId,
      });
      onDecision?.(accepted, Boolean(response.consensusReached));
      onClose?.();
    } catch {
      setError('Unable to record consent');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="border-b border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-lg font-bold text-slate-800">
              <Users className="h-5 w-5 text-blue-600" />
              Co-passenger consent
            </h3>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full bg-blue-600 transition-all"
                style={{ width: `${(timeLeft / request.timeoutSeconds) * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-slate-600">{timeLeft}s</span>
          </div>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-xl bg-blue-50 p-4">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-2xl font-bold text-blue-700">
                {request.requester.name.charAt(0)}
              </div>
              <div>
                <p className="font-semibold text-slate-800">{request.requester.name}</p>
                <p className="text-sm capitalize text-slate-600">
                  {request.requester.age} yrs · {request.requester.gender}
                </p>
                <p className="text-sm text-emerald-700">
                  Rating {request.requester.rating.toFixed(1)} · Safety {request.requester.safetyRating}/100
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3 text-sm">
            <div className="flex gap-3">
              <MapPin className="mt-0.5 h-4 w-4 text-emerald-600" />
              <div>
                <p className="text-xs text-slate-500">Pickup</p>
                <p className="font-medium">{request.pickup.address}</p>
              </div>
            </div>
            <div className="flex gap-3">
              <Clock className="h-4 w-4 text-amber-600" />
              <p>Detour +{request.estimatedDetourMinutes} mins</p>
            </div>
            <div className="flex gap-3">
              <DollarSign className="h-4 w-4 text-emerald-600" />
              <p>Joiner fare ₹{request.additionalFare.toFixed(0)}</p>
            </div>
          </div>

          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        </div>

        <div className="flex gap-3 border-t border-slate-200 p-4">
          <button
            disabled={loading}
            onClick={() => handleDecision(false)}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-red-100 py-3 font-medium text-red-700"
          >
            <X className="h-5 w-5" /> Reject
          </button>
          <button
            disabled={loading}
            onClick={() => handleDecision(true)}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 font-medium text-white"
          >
            <Check className="h-5 w-5" /> Accept
          </button>
        </div>
      </div>
    </div>
  );
};
