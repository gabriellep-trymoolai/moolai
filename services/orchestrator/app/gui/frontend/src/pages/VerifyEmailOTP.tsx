import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthCard } from '@/components/AuthCard';
import { AuthInput } from '@/components/AuthInput';
import { Button } from '@/components/ui/button';
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp';

// Backend base URL
const BACKEND = 'http://localhost:8000';

export const VerifyEmailOTP: React.FC = () => {
  const navigate = useNavigate();

  // Form state
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [step, setStep] = useState<'email' | 'otp'>('email');

  // UI state
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [codeSent, setCodeSent] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Start cooldown timer
  const startResendCooldown = () => {
    setResendCooldown(60); // 60 seconds
    const timer = setInterval(() => {
      setResendCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  // Send verification code
  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setBusy(true);

    try {
      const response = await fetch(`${BACKEND}/api/v1/auth/send-verification-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setSuccess(`Verification code sent to ${email}`);
        setCodeSent(true);
        setStep('otp');
        startResendCooldown();
      } else {
        setError(data.detail || data.message || 'Failed to send verification code');
      }
    } catch (err: any) {
      setError('Network error. Please check your connection and try again.');
      console.error('Send code error:', err);
    } finally {
      setBusy(false);
    }
  };

  // Verify OTP code
  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setBusy(true);

    try {
      const response = await fetch(`${BACKEND}/api/v1/auth/verify-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, code: otp }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setSuccess('Email verified successfully!');
        
        // Store user info if needed
        if (data.user_id) {
          localStorage.setItem('user_id', data.user_id);
          localStorage.setItem('user_email', data.email);
        }

        // Redirect after a short delay
        setTimeout(() => {
          navigate(data.redirect_url || '/profile-setup');
        }, 1500);
      } else {
        setError(data.detail || data.message || 'Invalid verification code');
      }
    } catch (err: any) {
      setError('Network error. Please check your connection and try again.');
      console.error('Verify code error:', err);
    } finally {
      setBusy(false);
    }
  };

  // Resend code
  const handleResendCode = async () => {
    if (resendCooldown > 0) return;
    
    setError(null);
    setSuccess(null);
    setOtp(''); // Clear the OTP input
    
    try {
      await handleSendCode(new Event('submit') as any);
    } catch (err) {
      console.error('Resend error:', err);
    }
  };

  // Go back to email step
  const handleBackToEmail = () => {
    setStep('email');
    setCodeSent(false);
    setOtp('');
    setError(null);
    setSuccess(null);
  };

  return (
    <AuthCard>
      <div className="text-center mb-8">
        <h1 className="text-2xl font-semibold text-foreground mb-2">
          {step === 'email' ? 'Verify your email' : 'Enter verification code'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {step === 'email' 
            ? 'Enter your email address to receive a verification code'
            : `We sent a 6-digit code to ${email}`
          }
        </p>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}
      
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          {success}
        </div>
      )}

      {/* Email Step */}
      {step === 'email' && (
        <form onSubmit={handleSendCode} className="space-y-6">
          <AuthInput
            label="Email Address"
            type="email"
            value={email}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            disabled={busy}
            className="bg-input"
          />

          <Button 
            type="submit" 
            className="w-full h-12"
            disabled={busy || !email}
          >
            {busy ? 'Sending Code...' : 'Send Verification Code'}
          </Button>
        </form>
      )}

      {/* OTP Step */}
      {step === 'otp' && (
        <form onSubmit={handleVerifyCode} className="space-y-6">
          {/* Show email with edit option */}
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Sending code to:</p>
                <p className="font-medium">{email}</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleBackToEmail}
                disabled={busy}
              >
                Edit
              </Button>
            </div>
          </div>

          {/* OTP Input */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Verification Code</label>
            <div className="flex justify-center">
              <InputOTP
                maxLength={6}
                value={otp}
                onChange={setOtp}
                className="gap-2"
                disabled={busy}
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
            <p className="mt-2 text-xs text-muted-foreground text-center">
              Enter the 6-digit code sent to your email
            </p>
          </div>

          <Button 
            type="submit" 
            className="w-full h-12"
            disabled={busy || otp.length !== 6}
          >
            {busy ? 'Verifying...' : 'Verify Email'}
          </Button>

          {/* Resend Code */}
          <div className="text-center">
            <p className="text-sm text-muted-foreground mb-2">
              Didn't receive the code?
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleResendCode}
              disabled={busy || resendCooldown > 0}
            >
              {resendCooldown > 0 
                ? `Resend in ${resendCooldown}s` 
                : 'Resend Code'
              }
            </Button>
          </div>
        </form>
      )}

      {/* Footer Links */}
      <div className="text-center mt-6">
        <p className="text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="text-orange-primary hover:text-orange-light">
            Log in
          </Link>
        </p>
      </div>
    </AuthCard>
  );
};