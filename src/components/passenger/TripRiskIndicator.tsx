import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle, Clock, Info, MapPin, Shield, Star, Sun, User } from 'lucide-react';
import { passengerApi } from '../../services/passengerApi';
import { GeoLocation, TripRiskScore, VehicleMode } from '../../types/commute';

interface TripRiskIndicatorProps {
  pickup: GeoLocation;
  dropoff: GeoLocation;
  vehicleType: VehicleMode;
  onRiskCalculated?: (riskScore: TripRiskScore) => void;
}

export const TripRiskIndicator: React.FC<TripRiskIndicatorProps> = ({
  pickup,
  dropoff,
  vehicleType,
  onRiskCalculated,
}) => {
  const [riskScore, setRiskScore] = useState<TripRiskScore | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const score = await passengerApi.getTripRiskScore(pickup, dropoff, vehicleType);
        if (!cancelled) {
          setRiskScore(score);
          onRiskCalculated?.(score);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [pickup.lat, pickup.lng, dropoff.lat, dropoff.lng, vehicleType]);

  const palette = {
    low: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    medium: 'border-amber-200 bg-amber-50 text-amber-800',
    high: 'border-red-200 bg-red-50 text-red-800',
  };

  const bar = (value: number) =>
    value >= 80 ? 'bg-emerald-500' : value >= 55 ? 'bg-amber-500' : 'bg-red-500';

  if (loading || !riskScore) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
        Calculating pre-ride AI risk score…
      </div>
    );
  }

  return (
    <div className={`rounded-xl border-2 p-4 ${palette[riskScore.score]}`}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {riskScore.score === 'low' ? <CheckCircle className="h-6 w-6" /> : <AlertTriangle className="h-6 w-6" />}
          <div>
            <h3 className="text-lg font-semibold">Trip Risk Score</h3>
            <p className="text-sm opacity-80">
              {riskScore.score.toUpperCase()} · route, lighting, incidents, driver, co-passengers
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold">{riskScore.scoreValue}</div>
          <div className="text-xs opacity-70">/ 100</div>
        </div>
      </div>

      <div className="space-y-3">
        {[
          { icon: MapPin, label: 'Route Safety Index', value: riskScore.factors.routeSafetyIndex },
          { icon: Clock, label: 'Time of Travel Risk', value: 100 - riskScore.factors.timeOfDayRisk },
          { icon: Sun, label: 'Street Lighting Index', value: riskScore.factors.streetLightingIndex },
          { icon: Shield, label: 'Historical Incidents (inverse)', value: 100 - riskScore.factors.historicalIncidentFrequency },
          { icon: User, label: 'Driver Safety Profile', value: riskScore.factors.driverSafetyProfile },
          { icon: Star, label: 'Co-Passenger Safety Index', value: riskScore.factors.coPassengerSafetyRating },
        ].map((row) => (
          <div key={row.label} className="flex items-center gap-3">
            <row.icon className="h-4 w-4 opacity-70" />
            <div className="flex-1">
              <div className="mb-1 flex justify-between text-sm">
                <span>{row.label}</span>
                <span className="font-medium">{row.value}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/60">
                <div className={`h-full ${bar(row.value)}`} style={{ width: `${Math.max(8, Math.min(100, row.value))}%` }} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 border-t border-current/20 pt-3">
        <h4 className="mb-2 flex items-center gap-2 text-sm font-medium">
          <Info className="h-4 w-4" /> Safety recommendations
        </h4>
        <ul className="space-y-1 text-sm">
          {riskScore.recommendations.map((item) => (
            <li key={item}>• {item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};
