export interface AuthenticatedUser {
  id: number;
  phone: string;
  role: 'passenger' | 'driver' | 'admin';
}

export interface AuthSession {
  accessToken: string;
  user: AuthenticatedUser;
}

let currentSession: AuthSession | null = null;
const listeners = new Set<() => void>();

export function getAuthSession(): AuthSession | null {
  return currentSession;
}

export function setAuthSession(session: AuthSession): void {
  currentSession = session;
  listeners.forEach((listener) => listener());
}

export function clearAuthSession(): void {
  if (!currentSession) return;
  currentSession = null;
  listeners.forEach((listener) => listener());
}

export function subscribeToAuthSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
