import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { PassengerApp } from './components/passenger/PassengerApp';
import { DriverApp } from './components/driver/DriverApp';
import { Navigation, Car, User } from 'lucide-react';
import './index.css';

// Home Page Component
const HomePage = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-800 mb-4">SIH 26203 · Intelligent Commutation</h1>
          <p className="text-lg text-gray-600">Smart Commutation Engine + Tourism Safety & Security System</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Passenger App Card */}
          <Link to="/passenger" className="bg-white rounded-2xl shadow-xl p-8 hover:shadow-2xl transition-all group">
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-blue-200 transition-colors">
                <User className="w-10 h-10 text-blue-600" />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Passenger App</h2>
              <p className="text-gray-600 mb-4">
                Book rides, track in real-time, and access safety features
              </p>
              <div className="text-sm text-blue-600 font-medium group-hover:underline">
                Open Passenger App →
              </div>
            </div>
          </Link>

          {/* Driver App Card */}
          <Link to="/driver" className="bg-white rounded-2xl shadow-xl p-8 hover:shadow-2xl transition-all group">
            <div className="flex flex-col items-center text-center">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-green-200 transition-colors">
                <Car className="w-10 h-10 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Driver App</h2>
              <p className="text-gray-600 mb-4">
                Manage rides, verify identity, and track earnings
              </p>
              <div className="text-sm text-green-600 font-medium group-hover:underline">
                Open Driver App →
              </div>
            </div>
          </Link>
        </div>

        {/* Features Section */}
        <div className="mt-12 bg-white rounded-2xl shadow-xl p-8">
          <h3 className="text-xl font-bold text-gray-800 mb-6 text-center">Key Features</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Navigation className="w-6 h-6 text-purple-600" />
              </div>
              <h4 className="font-semibold text-gray-800 mb-2">4 Vehicle Modes</h4>
              <p className="text-sm text-gray-600">Bike, Auto, Cab, Van with pooling support</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <User className="w-6 h-6 text-red-600" />
              </div>
              <h4 className="font-semibold text-gray-800 mb-2">AI Risk Prediction</h4>
              <p className="text-sm text-gray-600">Pre-ride safety scoring with recommendations</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Car className="w-6 h-6 text-yellow-600" />
              </div>
              <h4 className="font-semibold text-gray-800 mb-2">Smart Consolidation</h4>
              <p className="text-sm text-gray-600">Demand clustering for cost savings</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/passenger/*" element={<PassengerApp />} />
        <Route path="/driver/*" element={<DriverApp />} />
      </Routes>
    </Router>
  </React.StrictMode>,
);
