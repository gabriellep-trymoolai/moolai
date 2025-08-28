import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthCard } from '@/components/AuthCard';
import { AuthInput } from '@/components/AuthInput';
import { Button } from '@/components/ui/button';
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp';

// MSAL wiring
import { msal, apiScopes } from '../auth/msal';

// Backend base (adjust if your API runs on a different port)
const BACKEND = 'http://localhost:8000';

export const VerifyEmail: React.FC = () => {
  const navigate = useNavigate();

  // Keep your original UI state
  const [email, setEmail] = useState('aisvarya@gmail.com');
  const [otp, setOtp] = useState('');

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // After B2C redirects back here, complete the code flow and get an access token.
  useEffect(() => {
    (async () => {
      try {
        setBusy(true);
        // Completes the redirect flow (if we came back from B2C)
        await msal.handleRedirectPromise();

        const accounts = msal.getAllAccounts();
        if (!accounts.length) {
          // Not signed in yet (first visit), do nothing — user will click your button
          setBusy(false);
          return;
        }

        // Get access token silently
        const result = await msal.acquireTokenSilent({
          account: accounts[0],
          scopes: apiScopes,
        });

        const token = result.accessToken;
        (window as any).__B2C_TOKEN__ = token; // for curl testing in DevTools

        // Call your backend for sanity check (optional)
        await fetch(`${BACKEND}/api/v1/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        // Proceed with your original flow
        navigate('/profile-setup');
      } catch (e: any) {
        // If silent fails because we're not signed in yet, that's fine — user will click your button
        if (e?.errorCode && String(e.errorCode).includes('no_tokens_found')) {
          setError(null);
        } else {
          console.error(e);
          setError(e?.message || String(e));
        }
      } finally {
        setBusy(false);
      }
    })();
  }, [navigate]);

  // Your original submit handler → now triggers B2C hosted UI
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await msal.loginRedirect({
        scopes: apiScopes,
        loginHint: email || undefined, // pre-fill email on B2C page
      });
      // No further code runs here because we redirect to B2C
    } catch (e: any) {
      console.error(e);
      setBusy(false);
      setError(e?.message || String(e));
    }
  };

  return (
    <AuthCard>
      <div className="text-center mb-8">
        <h1 className="text-2xl font-semibold text-foreground mb-2">Verify your email</h1>
        <p className="text-sm text-muted-foreground">Enter the one-time code to create an account</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <AuthInput
          label="Email ID"
          type="email"
          value={email}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          disabled={busy}
          className="bg-input"
        />

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Verification Code</label>
          <div className="flex justify-center">
            <InputOTP
              maxLength={6}
              value={otp}
              onChange={setOtp}
              className="gap-2"
            >
              <InputOTPGroup className="gap-2">
                {[...Array(6)].map((_, index) => (
                  <InputOTPSlot
                    key={index}
                    index={index}
                    className="w-12 h-12 bg-input border-border text-foreground text-center rounded-lg"
                  />
                ))}
              </InputOTPGroup>
            </InputOTP>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Code entry is handled by Azure AD B2C during sign-up/MFA on the hosted page.
          </p>
        </div>


        <Button 
          type="submit" 
          className="w-full h-12"
          disabled={busy}
        >
          {busy ? 'Redirecting…' : 'Verify & Continue'}
        </Button>
      </form>

      <div className="text-center mt-6">
        <p className="text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="text-orange-primary hover:text-orange-light">
            Log in
          </Link>
        </p>
      </div>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-card px-3 text-muted-foreground">Or</span>
        </div>
      </div>

      <Button 
        variant="outline" 
        className="w-full h-12 bg-secondary border-border text-foreground hover:bg-input"
        type="button"
        onClick={() => msal.loginRedirect({ scopes: apiScopes })}
        disabled={busy}
      >
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 bg-white rounded-full flex items-center justify-center">
            <span className="text-xs font-bold text-blue-600">G</span>
          </div>
          Sign up with Google
        </div>
      </Button>
    </AuthCard>
  );
};
