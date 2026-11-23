import { clearAuthSession, getAuthSession } from './authSession';

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const session = getAuthSession();
  if (!session) throw new Error('Authentication required. Please sign in again.');

  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${session.accessToken}`);
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) clearAuthSession();
  return response;
}
