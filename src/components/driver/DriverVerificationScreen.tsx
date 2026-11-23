import React, { useState } from 'react';
import { AlertTriangle, Lock, X } from 'lucide-react';
import { driverApi } from '../../services/driverApi';

interface DriverVerificationScreenProps {
  driverId: string;
  rideId: string;
  onVerificationSuccess?: () => void;
  onCancel?: () => void;
}

export const DriverVerificationScreen: React.FC<DriverVerificationScreenProps> = ({
  driverId,
  rideId,
  onVerificationSuccess,
  onCancel,
}) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkVerificationService = async () => {
    setBusy(true);
    setError(null);
    const response = await driverApi.verifyIdentity({
      rideId,
      driverId,
      verificationMethod: 'facial',
    });
    setBusy(false);
    if (response.verified) onVerificationSuccess?.();
    else setError(response.error || 'Identity verification did not succeed. OTP remains locked.');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-lg font-bold">
            <Lock className="h-5 w-5 text-amber-700" /> Driver identity check
          </h3>
          <button onClick={onCancel} aria-label="Close verification">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4" /> Verification service unavailable
          </p>
          <p className="mt-2">
            An authorized face-identity model is not configured. No camera frame or biometric fallback
            will be collected, and the trip OTP will remain locked.
          </p>
        </div>
        <button
          disabled={busy}
          onClick={() => void checkVerificationService()}
          className="mt-4 w-full rounded-xl bg-slate-800 py-3 font-medium text-white disabled:opacity-50"
        >
          {busy ? 'Checking backend…' : 'Check verification service'}
        </button>
        {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
};
