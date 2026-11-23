import { useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { logout } from '../../services/authApi';
import { getAuthSession, subscribeToAuthSession } from '../../services/authSession';
import { LoginScreen } from './LoginScreen';

interface RequireAuthProps {
  role: 'passenger' | 'driver';
  children: ReactNode;
}

export function RequireAuth({ role, children }: RequireAuthProps) {
  const session = useSyncExternalStore(subscribeToAuthSession, getAuthSession, () => null);
  const navigate = useNavigate();
  if (!session) return <LoginScreen role={role} />;
  if (session.user.role !== role) {
    return (
      <main className="p-8">
        <p role="alert">This account is not authorized for the {role} app.</p>
        <button
          className="mt-4 rounded bg-slate-800 px-4 py-2 text-white"
          onClick={() => void logout().then(() => navigate('/'))}
        >
          Sign out
        </button>
      </main>
    );
  }
  return (
    <>
      <div className="fixed right-4 top-4 z-50">
        <button
          className="rounded border bg-white px-3 py-2 text-sm"
          onClick={() => void logout().then(() => navigate('/'))}
        >
          Sign out
        </button>
      </div>
      {children}
    </>
  );
}
