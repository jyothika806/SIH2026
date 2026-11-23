import { clearAuthSession, setAuthSession } from './authSession';
import { authenticatedFetch } from './authenticatedFetch';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function postAuth(endpoint: string, body: unknown): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(body),
  });
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    clearAuthSession();
    const detail = payload.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Authentication request failed');
  }
  return payload;
}

export async function requestLoginOtp(phone: string): Promise<void> {
  await postAuth('/api/v1/auth/request-otp', { phone, delivery_method: 'sms' });
}

export async function verifyLoginOtp(
  phone: string,
  otp: string,
  role: 'passenger' | 'driver',
): Promise<void> {
  const payload = await postAuth('/api/v1/auth/verify-otp', { phone, otp, role });
  const user = payload.user as Record<string, unknown> | undefined;
  if (
    typeof payload.access_token !== 'string' ||
    !user ||
    typeof user.id !== 'number' ||
    typeof user.phone !== 'string' ||
    (user.role !== 'passenger' && user.role !== 'driver' && user.role !== 'admin')
  ) {
    clearAuthSession();
    throw new Error('Authentication service returned an invalid session');
  }
  setAuthSession({
    accessToken: payload.access_token,
    user: {
      id: user.id,
      phone: user.phone,
      role: user.role,
    },
  });
}

export async function logout(): Promise<void> {
  try {
    await authenticatedFetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: 'POST' });
  } finally {
    clearAuthSession();
  }
}
