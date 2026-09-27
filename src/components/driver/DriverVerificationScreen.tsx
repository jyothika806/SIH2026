import React, { useEffect, useRef, useState } from 'react';
import { Camera, Check, Fingerprint, Lock, Unlock, X } from 'lucide-react';
import { driverApi } from '../../services/driverApi';

interface DriverVerificationScreenProps {
  driverId: string;
  onVerificationSuccess?: (otp: string) => void;
  onCancel?: () => void;
}

export const DriverVerificationScreen: React.FC<DriverVerificationScreenProps> = ({
  driverId,
  onVerificationSuccess,
  onCancel,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [otp, setOtp] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cameraOn || !videoRef.current) return;
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: true })
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch(() => setError('Camera blocked — use biometric fallback'));
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, [cameraOn]);

  const submit = async (method: 'facial' | 'biometric', facialData?: string) => {
    setBusy(true);
    setError(null);
    const response = await driverApi.verifyIdentity({
      driverId,
      verificationMethod: method,
      facialData,
      biometricData: method === 'biometric' ? 'webauthn-sim' : undefined,
    });
    setBusy(false);
    if (response.verified) {
      setOtp(response.otpUnlocked || '4567');
      window.setTimeout(() => onVerificationSuccess?.(response.otpUnlocked || '4567'), 900);
    } else setError(response.error || 'Verification failed');
  };

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    canvas.getContext('2d')?.drawImage(video, 0, 0);
    void submit('facial', canvas.toDataURL('image/jpeg'));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-lg font-bold">
            {otp ? <Unlock className="h-5 w-5 text-emerald-600" /> : <Lock className="h-5 w-5 text-blue-600" />}
            {otp ? 'Identity verified' : 'Driver face scan'}
          </h3>
          <button onClick={onCancel}>
            <X className="h-5 w-5" />
          </button>
        </div>

        {otp ? (
          <div className="text-center">
            <Check className="mx-auto mb-3 h-12 w-12 text-emerald-600" />
            <p className="text-sm text-slate-500">Trip start OTP unlocked</p>
            <p className="mt-2 text-5xl font-bold tracking-[0.35em]">{otp}</p>
          </div>
        ) : (
          <>
            <div className="relative mb-4 aspect-video overflow-hidden rounded-xl bg-slate-900">
              {cameraOn ? (
                <video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-cover" />
              ) : (
                <button onClick={() => setCameraOn(true)} className="flex h-full w-full items-center justify-center text-white">
                  <Camera className="mr-2 h-5 w-5" /> Start live camera
                </button>
              )}
              <canvas ref={canvasRef} className="hidden" />
            </div>
            <button
              disabled={busy || !cameraOn}
              onClick={capture}
              className="mb-2 w-full rounded-xl bg-blue-600 py-3 font-medium text-white disabled:opacity-50"
            >
              {busy ? 'Matching OpenCV payload…' : 'Capture face scan'}
            </button>
            <button
              disabled={busy}
              onClick={() => submit('biometric')}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-100 py-3 font-medium"
            >
              <Fingerprint className="h-5 w-5" /> Biometric device fallback
            </button>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </>
        )}
      </div>
    </div>
  );
};
