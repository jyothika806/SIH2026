import { FormEvent, useState } from 'react';
import { requestLoginOtp, verifyLoginOtp } from '../../services/authApi';

interface LoginScreenProps {
  role: 'passenger' | 'driver';
}

export function LoginScreen({ role }: LoginScreenProps) {
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpRequested, setOtpRequested] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (!otpRequested) {
        await requestLoginOtp(phone);
        setOtpRequested(true);
      } else {
        await verifyLoginOtp(phone, otp, role);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Sign-in failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <form className="w-full max-w-md rounded-xl bg-white p-8 shadow" onSubmit={submit}>
        <h1 className="mb-2 text-2xl font-semibold">Sign in as {role}</h1>
        <p className="mb-6 text-sm text-slate-600">
          A verified account and SMS access are required. Reloading this page signs you out.
        </p>
        <label className="mb-4 block text-sm font-medium">
          Phone number
          <input
            autoComplete="tel"
            className="mt-1 w-full rounded border p-2"
            onChange={(event) => setPhone(event.target.value)}
            required
            value={phone}
          />
        </label>
        {otpRequested && (
          <label className="mb-4 block text-sm font-medium">
            SMS code
            <input
              autoComplete="one-time-code"
              className="mt-1 w-full rounded border p-2"
              inputMode="numeric"
              maxLength={6}
              onChange={(event) => setOtp(event.target.value)}
              pattern="[0-9]{6}"
              required
              value={otp}
            />
          </label>
        )}
        {error && <p role="alert" className="mb-4 text-sm text-red-700">{error}</p>}
        <button className="w-full rounded bg-blue-700 p-3 font-semibold text-white disabled:opacity-50" disabled={busy}>
          {busy ? 'Please wait...' : otpRequested ? 'Verify and sign in' : 'Send SMS code'}
        </button>
      </form>
    </main>
  );
}
