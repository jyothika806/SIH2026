import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, Copy, Phone, Share2, Shield, Volume2, VolumeX, X } from 'lucide-react';
import { passengerApi } from '../../services/passengerApi';
import { GeoLocation } from '../../types/commute';

interface SafetyFeaturesProps {
  rideId?: string;
  currentLocation?: GeoLocation;
  shareLink?: string;
  source?: 'passenger' | 'driver';
}

function useSiren(active: boolean, muted: boolean) {
  const ctx = useRef<AudioContext | null>(null);
  const osc = useRef<OscillatorNode[]>([]);

  useEffect(() => {
    const stop = () => {
      osc.current.forEach((o) => {
        try {
          o.stop();
          o.disconnect();
        } catch {
          /* ignore */
        }
      });
      osc.current = [];
      void ctx.current?.close();
      ctx.current = null;
    };

    if (!active || muted) {
      stop();
      return stop;
    }

    const audio = new AudioContext();
    ctx.current = audio;
    const gain = audio.createGain();
    gain.gain.value = 0.28;
    gain.connect(audio.destination);
    const o1 = audio.createOscillator();
    const o2 = audio.createOscillator();
    o1.type = 'sawtooth';
    o2.type = 'square';
    o1.connect(gain);
    o2.connect(gain);
    o1.start();
    o2.start();
    osc.current = [o1, o2];
    const pulse = () => {
      if (!ctx.current) return;
      const t = audio.currentTime;
      o1.frequency.setValueAtTime(800, t);
      o1.frequency.linearRampToValueAtTime(1200, t + 0.45);
      o2.frequency.setValueAtTime(560, t);
      o2.frequency.linearRampToValueAtTime(920, t + 0.45);
    };
    pulse();
    const id = window.setInterval(pulse, 500);
    return () => {
      window.clearInterval(id);
      stop();
    };
  }, [active, muted]);
}

export const SafetyFeatures: React.FC<SafetyFeaturesProps> = ({
  rideId,
  currentLocation,
  shareLink,
}) => {
  const [countdown, setCountdown] = useState(0);
  const [armed, setArmed] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const [muted, setMuted] = useState(false);
  const [copied, setCopied] = useState(false);
  const generatedLink = shareLink || (rideId ? `${window.location.origin}/passenger/track/${rideId}` : '');

  useSiren(triggered, muted);

  useEffect(() => {
    if (!armed || countdown <= 0) {
      if (armed && countdown === 0) void dispatch();
      return;
    }
    const t = window.setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [armed, countdown]);

  const dispatch = async () => {
    setArmed(false);
    setTriggered(true);
    await passengerApi.triggerSOS({
      rideId,
      location: currentLocation || { lat: 12.9716, lng: 77.5946 },
      emergencyType: 'panic',
    });
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-bold">
          <Shield className="h-5 w-5 text-red-600" /> Emergency SOS
        </h3>
        {triggered ? (
          <div className="text-center">
            <AlertTriangle className="mx-auto mb-2 h-10 w-10 animate-pulse text-red-600" />
            <p className="font-bold text-red-700">Security center alerted</p>
            <button onClick={() => setMuted((m) => !m)} className="mt-3 inline-flex items-center gap-2 text-sm">
              {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />} {muted ? 'Unmute siren' : 'Mute siren'}
            </button>
          </div>
        ) : armed ? (
          <div className="text-center">
            <div className="mx-auto mb-3 flex h-24 w-24 items-center justify-center rounded-full bg-red-600 text-4xl font-bold text-white">
              {countdown}
            </div>
            <button onClick={() => setArmed(false)} className="rounded-lg bg-slate-200 px-4 py-2">
              <X className="mr-1 inline h-4 w-4" /> Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => {
              setArmed(true);
              setCountdown(5);
            }}
            className="w-full rounded-xl bg-red-600 py-4 font-bold text-white"
          >
            SOS · 5s countdown
          </button>
        )}
      </div>

      {generatedLink && (
        <div className="rounded-2xl bg-white p-6 shadow-xl">
          <h3 className="mb-3 flex items-center gap-2 font-bold">
            <Share2 className="h-5 w-5 text-blue-600" /> Share trip
          </h3>
          <div className="flex gap-2">
            <input readOnly value={generatedLink} className="flex-1 truncate rounded-lg border px-3 py-2 text-xs" />
            <button
              onClick={async () => {
                await navigator.clipboard.writeText(generatedLink);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              }}
              className="rounded-lg bg-blue-600 px-3 py-2 text-white"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
        </div>
      )}

      <div className="rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="mb-3 flex items-center gap-2 font-bold">
          <Phone className="h-5 w-5 text-purple-600" /> Speed dial
        </h3>
        <div className="space-y-2">
          <a href="tel:112" className="block rounded-lg bg-red-50 py-3 text-center font-medium text-red-700">
            Police / ERSS 112
          </a>
          <a href="tel:1363" className="block rounded-lg bg-blue-50 py-3 text-center font-medium text-blue-700">
            Tourist Helpline 1363
          </a>
          <a href="tel:1091" className="block rounded-lg bg-emerald-50 py-3 text-center font-medium text-emerald-700">
            Women Helpline 1091
          </a>
        </div>
      </div>
    </div>
  );
};

export { useSiren };
