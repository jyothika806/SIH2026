import React from 'react';
import { Link, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Navigation, Shield } from 'lucide-react';
import { BookingInterface } from './BookingInterface';
import { LiveRideTracking } from './LiveRideTracking';
import { SafetyFeatures } from './SafetyFeatures';

const BookingPage = () => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <header className="bg-white shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-2">
            <Navigation className="h-7 w-7 text-blue-600" />
            <div>
              <h1 className="text-xl font-bold">Passenger</h1>
              <p className="text-xs text-slate-500">SIH 26203 · Smart Commutation</p>
            </div>
          </div>
          <Link to="/" className="font-medium text-blue-600">
            Home
          </Link>
        </div>
      </header>
      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <BookingInterface onRideBooked={(id) => navigate(`/passenger/track/${id}`)} />
        </div>
        <SafetyFeatures />
      </main>
    </div>
  );
};

const TrackingPage = () => {
  const { rideId } = useParams<{ rideId: string }>();
  const navigate = useNavigate();
  if (!rideId) return null;
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <header className="bg-white shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <button onClick={() => navigate('/passenger')} className="flex items-center gap-2 text-slate-600">
            <ArrowLeft className="h-5 w-5" /> Booking
          </button>
          <span className="flex items-center gap-2 text-sm font-medium text-emerald-700">
            <Shield className="h-5 w-5" /> Tracking {rideId.slice(-6)}
          </span>
        </div>
      </header>
      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <LiveRideTracking rideId={rideId} onRideComplete={() => navigate('/passenger')} />
        </div>
        <SafetyFeatures rideId={rideId} />
      </main>
    </div>
  );
};

export const PassengerApp: React.FC = () => (
  <Routes>
    <Route index element={<BookingPage />} />
    <Route path="track/:rideId" element={<TrackingPage />} />
  </Routes>
);
