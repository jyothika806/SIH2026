import React from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { Car } from 'lucide-react';
import { DriverDashboard } from './DriverDashboard';
import { DriverNavigation } from './DriverNavigation';

const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-slate-100">
    <header className="bg-white shadow-sm">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4">
        <div className="flex items-center gap-2">
          <Car className="h-7 w-7 text-emerald-600" />
          <div>
            <h1 className="text-xl font-bold">Driver</h1>
            <p className="text-xs text-slate-500">SIH 26203 · Tourism Safety Gateway</p>
          </div>
        </div>
        <Link to="/" className="font-medium text-emerald-700">
          Home
        </Link>
      </div>
    </header>
    <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
  </div>
);

export const DriverApp: React.FC = () => (
  <Routes>
    <Route
      index
      element={
        <Shell>
          <DriverDashboard />
        </Shell>
      }
    />
    <Route
      path="active-ride"
      element={
        <Shell>
          <DriverNavigation />
        </Shell>
      }
    />
  </Routes>
);
