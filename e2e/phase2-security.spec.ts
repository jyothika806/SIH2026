import { expect, test, type Page } from '@playwright/test';

async function loginThroughStack(
  page: Page,
  role: 'passenger' | 'driver',
  phone: string | undefined,
) {
  test.skip(
    process.env.PHASE2_E2E_READY !== '1',
    'Requires the disposable phase2_e2e database',
  );
  const accountPhone =
    phone || (role === 'passenger' ? '+14155552675' : '+14155552676');
  const registration = await page.request.post(
    'http://127.0.0.1:18080/api/v1/auth/register',
    { data: { phone: accountPhone, role } },
  );
  expect([201, 409]).toContain(registration.status());
  await page.goto(`/${role}`);
  await page.getByLabel('Phone number').fill(accountPhone);
  const otpRequest = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/auth/request-otp') &&
      response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Send SMS code' }).click();
  expect((await otpRequest).ok()).toBe(true);
  const smsResponse = await page.request.get(
    `http://127.0.0.1:18890/messages?phone=${encodeURIComponent(accountPhone)}`,
  );
  expect(smsResponse.ok()).toBe(true);
  const sms = (await smsResponse.json()) as { message: string };
  const code = sms.message.match(/verification code is: (\d{6})/)?.[1];
  expect(code).toBeTruthy();
  await page.getByLabel('SMS code').fill(code!);
  const verificationResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/v1/auth/verify-otp') &&
      response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Verify and sign in' }).click();
  const verification = await verificationResponse;
  expect(verification.ok(), await verification.text()).toBe(true);
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  const accessToken = await page.evaluate(async () => {
    const { getAuthSession } = await import('/src/services/authSession.ts');
    return getAuthSession()?.accessToken ?? null;
  });
  expect(accessToken).toBeTruthy();
  return { accessToken: accessToken!, code: code!, phone: accountPhone };
}

async function seedRide(page: Page, rideId = '1') {
  await page.evaluate(async (id) => {
    const { bookRide } = await import('/src/engine/commuteEngine.ts');
    bookRide({
      pickup: { lat: 12.9716, lng: 77.5946 },
      dropoff: { lat: 12.9352, lng: 77.6245 },
      vehicleType: 'cab',
    });
    const key = 'sih2026.commute.engine.v1';
    const state = JSON.parse(localStorage.getItem(key) || '{}');
    state.activeRide.rideId = id;
    localStorage.setItem(key, JSON.stringify(state));
  }, rideId);
}

async function navigateSpa(page: Page, path: string) {
  await page.evaluate((target) => {
    window.history.pushState(null, '', target);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, path);
}

async function createBackendRide(page: Page): Promise<string> {
  const result = await page.evaluate(async () => {
    const { authenticatedFetch } = await import('/src/services/authenticatedFetch.ts');
    const response = await authenticatedFetch('http://127.0.0.1:18080/api/v1/rides/book', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
      body: JSON.stringify({
        pickup_lat: 12.9716,
        pickup_lon: 77.5946,
        dropoff_lat: 12.9352,
        dropoff_lon: 77.6245,
        vehicle_type: 'cab',
        seats_required: 1,
        is_mid_route: false,
      }),
    });
    const body = (await response.json().catch(() => ({}))) as { id?: number };
    return { status: response.status, id: body.id };
  });
  expect(result.status).toBe(201);
  expect(typeof result.id).toBe('number');
  return String(result.id);
}

test('passenger OTP retrieval stays locked when the backend refuses verification', async ({ page }) => {
  await loginThroughStack(
    page,
    'passenger',
    process.env.PHASE2_E2E_PASSENGER_PHONE || process.env.PHASE2_E2E_TEST_PHONE,
  );
  const rideId = await createBackendRide(page);
  await seedRide(page, rideId);
  await navigateSpa(page, `/passenger/track/${rideId}`);
  await expect(page.getByText('Trip start OTP')).toBeVisible();
  await expect(page.getByText('••••••')).toBeVisible();
  await page.getByRole('button', { name: 'Retrieve trip OTP' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByText('••••••')).toBeVisible();
  await expect(page.getByText(/Identity verified — OTP unlocked/)).toHaveCount(0);
});

test('driver verification failure never unlocks the local ride OTP', async ({ page }) => {
  const { accessToken } = await loginThroughStack(
    page,
    'driver',
    process.env.PHASE2_E2E_DRIVER_PHONE,
  );
  await seedRide(page);
  await navigateSpa(page, '/driver/active-ride');
  await page.getByRole('button', { name: 'Open identity verification' }).click();
  await page.getByRole('button', { name: 'Check verification service' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByText('Verification service unavailable')).toBeVisible();
  await expect(page.getByText(/Trip start OTP unlocked/)).toHaveCount(0);

  const response = await page.request.post(
    'http://127.0.0.1:18080/api/v1/liveness/request-verification',
    {
      data: { ride_id: 1 },
    headers: { Authorization: `Bearer ${accessToken}` },
    },
  );
  expect(response.status()).toBe(503);
  expect(await response.json()).toMatchObject({
    detail: 'Driver identity verification is unavailable; OTP remains locked',
  });
});

test('real login OTP round trip traverses the browser, Express gateway and FastAPI', async ({
  page,
}) => {
  const phone =
    process.env.PHASE2_E2E_PASSENGER_PHONE || process.env.PHASE2_E2E_TEST_PHONE;
  const { accessToken, code, phone: authenticatedPhone } = await loginThroughStack(
    page,
    'passenger',
    phone,
  );
  const currentUser = await page.evaluate(async () => {
    const { authenticatedFetch } = await import('/src/services/authenticatedFetch.ts');
    const response = await authenticatedFetch('http://127.0.0.1:18080/api/v1/auth/me');
    return response.status;
  });
  const replay = await page.request.post('http://127.0.0.1:18080/api/v1/auth/verify-otp', {
    data: { phone: authenticatedPhone, otp: code, role: 'passenger' },
  });
  const failureClearedSession = await page.evaluate(async () => {
    const { getAuthSession, setAuthSession } = await import('/src/services/authSession.ts');
    const { authenticatedFetch } = await import('/src/services/authenticatedFetch.ts');
    const session = getAuthSession();
    if (!session) return false;
    setAuthSession({ ...session, accessToken: 'invalid-test-token' });
    const response = await authenticatedFetch('http://127.0.0.1:18080/api/v1/auth/me');
    return response.status === 401 && getAuthSession() === null;
  });
  expect(currentUser).toBe(200);
  expect(accessToken.length).toBeGreaterThan(32);
  expect(replay.status()).toBe(401);
  expect(failureClearedSession).toBe(true);

  await page.reload();
  await expect(page.getByLabel('Phone number')).toBeVisible();
  const persistedToken = await page.evaluate(() =>
    `${localStorage.getItem('accessToken') || ''}${sessionStorage.getItem('accessToken') || ''}`,
  );
  expect(persistedToken).toBe('');
});

test('passenger status refresh preserves pooling, consent and mid-route state without a refresh loop', async ({
  page,
}) => {
  await loginThroughStack(
    page,
    'passenger',
    process.env.PHASE2_E2E_PASSENGER_PHONE || process.env.PHASE2_E2E_TEST_PHONE,
  );
  await seedRide(page);
  const result = await page.evaluate(async () => {
    const key = 'sih2026.commute.engine.v1';
    const stored = JSON.parse(localStorage.getItem(key) || '{}');
    stored.activeRide.status = 'trip_started';
    stored.activeRide.openSeats = 2;
    stored.activeRide.occupiedSeats = stored.activeRide.capacity - 2;
    localStorage.setItem(key, JSON.stringify(stored));

    const { subscribeEngine } = await import('/src/engine/commuteEngine.ts');
    const { passengerApi } = await import('/src/services/passengerApi.ts');
    let notifications = 0;
    const unsubscribe = subscribeEngine(() => {
      notifications += 1;
    });

    const stream = await passengerApi.streamStatus(stored.activeRide.rideId, {
      lat: 12.97,
      lng: 77.59,
    });
    const streamNotifications = notifications;
    const poolBefore = await passengerApi.listActiveRides();
    const consolidation = await passengerApi.getConsolidationSuggestion('auto');
    const join = await passengerApi.requestMidRideJoin({
      rideId: stored.activeRide.rideId,
      pickup: { lat: 12.96, lng: 77.6 },
      dropoff: stored.activeRide.dropoff,
    });
    const pending = passengerApi.getPendingConsent(stored.activeRide.passengerIds[0]);
    const consent = await passengerApi.submitMidRideConsent({
      requestId: join.requestId,
      rideId: stored.activeRide.rideId,
      consent: 'accept',
      passengerId: stored.activeRide.passengerIds[0],
    });
    const waypoint = (await import('/src/engine/commuteEngine.ts')).acceptWaypoint(
      join.requestId,
    );
    const poolAfter = await passengerApi.listActiveRides();
    unsubscribe();
    return {
      stream,
      streamNotifications,
      poolBefore: poolBefore.length,
      poolAfter: poolAfter.length,
      consolidationCount: consolidation.length,
      pendingStatus: pending?.status,
      consentSuccess: consent.success,
      waypointSuccess: waypoint.success,
      finalOpenSeats: poolAfter[0]?.openSeats,
    };
  });

  expect(result.stream.success).toBe(true);
  expect(result.streamNotifications).toBe(0);
  expect(result.poolBefore).toBe(1);
  expect(result.poolAfter).toBe(1);
  expect(result.consolidationCount).toBeGreaterThan(0);
  expect(result.pendingStatus).toBe('pending_consent');
  expect(result.consentSuccess).toBe(true);
  expect(result.waypointSuccess).toBe(true);
  expect(result.finalOpenSeats).toBe(1);
});

test('backend ride-start failure does not mutate the client ride state', async ({ page }) => {
  await loginThroughStack(page, 'driver', process.env.PHASE2_E2E_DRIVER_PHONE);
  await seedRide(page);
  const result = await page.evaluate(async () => {
    const { driverApi } = await import('/src/services/driverApi.ts');
    const start = await driverApi.startRide({
      rideId: '1',
      driverId: 'driver-001',
      otp: '123456',
      currentLocation: { lat: 12.9716, lng: 77.5946 },
    });
    const { getEngineState } = await import('/src/engine/commuteEngine.ts');
    const ride = getEngineState().activeRide;
    return {
      start,
      rideStatus: ride?.status,
      otpLocked: ride?.otpLocked,
      otp: ride?.otp,
      identityVerified: ride?.identityVerified,
    };
  });
  expect(result.start.success).toBe(false);
  expect(result.start.rideStarted).toBe(false);
  expect(result.rideStatus).toBe('driver_assigned');
  expect(result.otpLocked).toBe(true);
  expect(result.otp).toBeUndefined();
  expect(result.identityVerified).toBe(false);
});

test('Express fails closed without leaking upstream details when FastAPI is unavailable', async ({
  request,
}) => {
  const response = await request.post(
    'http://127.0.0.1:18081/api/v1/auth/request-otp',
    { data: { phone: '+14155552671', delivery_method: 'sms' } },
  );
  const body = await response.text();
  expect(response.status()).toBe(503);
  expect(response.headers()['cache-control']).toBe('no-store');
  expect(response.headers()['pragma']).toBe('no-cache');
  expect(body).not.toContain('127.0.0.1:18766');
  expect(body).not.toContain('ECONNREFUSED');
});
