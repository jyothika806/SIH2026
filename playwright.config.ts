import { defineConfig } from '@playwright/test';

const backendPort = 18765;
const gatewayPort = 18080;
const frontendPort = 14173;
const smsSinkPort = 18890;
const osrmStubPort = 18891;
const backendPython = process.env.PHASE2_PYTHON
  ? `"${process.env.PHASE2_PYTHON}"`
  : 'python';
const fallbackDatabaseUrl =
  'postgresql+asyncpg://phase2_test:phase2-test-only@127.0.0.1:55432/phase2_e2e';
const databaseUrl = process.env.PHASE2_E2E_DATABASE_URL || fallbackDatabaseUrl;
const parsedDatabaseUrl = new URL(databaseUrl);

if (
  !['127.0.0.1', 'localhost', '[::1]'].includes(parsedDatabaseUrl.hostname) ||
  parsedDatabaseUrl.port !== '55432' ||
  parsedDatabaseUrl.pathname !== '/phase2_e2e'
) {
  throw new Error(
    'E2E tests require the disposable local phase2_e2e database on port 55432.',
  );
}

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    browserName: 'chromium',
  },
  webServer: [
    {
      command: `python e2e\\osrm_stub.py --port ${osrmStubPort}`,
      url: `http://127.0.0.1:${osrmStubPort}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `${backendPython} -m uvicorn backend.app.main:app --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ENVIRONMENT: 'test',
        DATABASE_URL: databaseUrl,
        JWT_SECRET_KEY: 'playwright-test-jwt-secret-not-for-production',
        OTP_HMAC_KEY: 'playwright-test-otp-hmac-secret-not-for-production',
        LICENCE_HMAC_KEY: 'playwright-test-licence-hmac-secret-not-for-production',
        FERNET_KEY: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        REDIS_URL: 'redis://127.0.0.1:56379/0',
        OSRM_SERVER_URL: `http://127.0.0.1:${osrmStubPort}`,
        TEST_SMS_SINK_URL: `http://127.0.0.1:${smsSinkPort}/messages`,
        AUTO_CREATE_SCHEMA: 'true',
      },
    },
    {
      command: `python e2e\\sms_sink.py --port ${smsSinkPort}`,
      url: `http://127.0.0.1:${smsSinkPort}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `node dist\\server.js`,
      url: `http://127.0.0.1:${gatewayPort}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        PORT: String(gatewayPort),
        FASTAPI_SERVICE_URL: `http://127.0.0.1:${backendPort}`,
      },
    },
    {
      command: `node dist\\server.js`,
      url: 'http://127.0.0.1:18081/health',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        PORT: '18081',
        NODE_ENV: 'development',
        FASTAPI_SERVICE_URL: 'http://127.0.0.1:18766',
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_API_BASE_URL: `http://127.0.0.1:${gatewayPort}`,
      },
    },
  ],
});
