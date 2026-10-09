import React, { useState, useEffect, useRef } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { ThemeToggle } from '../ThemeToggle';
import homecartelLogo from '@/assets/homecartel_logo.png';

interface LoginScreenProps {
  onLoginSuccess: (pin: string) => void;
  authRequired: boolean;
  isLoadingConfig?: boolean;
}

export function LoginScreen({
  onLoginSuccess,
  authRequired,
  isLoadingConfig = false,
}: LoginScreenProps) {
  const [pin, setPin] = useState('');
  const [showPin, setShowPin] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoadingConfig && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoadingConfig]);

  const handleVerify = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);

    if (!authRequired) {
      onLoginSuccess(pin.trim());
      return;
    }

    const candidate = pin.trim();
    if (!candidate) {
      setError('Please enter your PIN');
      inputRef.current?.focus();
      return;
    }

    setIsVerifying(true);

    try {
      const res = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pin: candidate }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok && data.valid) {
        onLoginSuccess(candidate);
      } else {
        setError(data.error || 'Incorrect PIN. Please try again.');
        inputRef.current?.select();
      }
    } catch {
      setError('Could not connect to server.');
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col justify-between items-center p-4">
      {/* Top right theme toggle */}
      <div className="w-full flex justify-end p-2">
        <ThemeToggle />
      </div>

      {/* Clean Login Card */}
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 sm:p-8 shadow-xs">
        <div className="text-center mb-6">
          <img
            src={homecartelLogo}
            alt="HomeCartel"
            className="h-7 w-auto mx-auto mb-4 invert dark:invert-0 object-contain"
          />
          <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Marketing Studio
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {authRequired ? 'Enter your PIN to continue' : 'Open access studio'}
          </p>
        </div>

        <form onSubmit={handleVerify} className="space-y-4">
          {authRequired ? (
            <div className="space-y-1.5">
              <label
                htmlFor="pin"
                className="block text-xs font-medium text-slate-700 dark:text-slate-300"
              >
                PIN
              </label>
              <div className="relative">
                <input
                  ref={inputRef}
                  id="pin"
                  type={showPin ? 'text' : 'password'}
                  value={pin}
                  onChange={(e) => {
                    setPin(e.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="Enter PIN"
                  disabled={isVerifying}
                  className="w-full px-3 py-2 pr-9 text-sm border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900 dark:focus:ring-slate-300 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPin(!showPin)}
                  tabIndex={-1}
                  className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                >
                  {showPin ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          ) : null}

          {error && (
            <div className="p-2.5 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-xs text-red-600 dark:text-red-400">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isVerifying || isLoadingConfig}
            className="w-full mt-2 py-2 px-4 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-white dark:hover:bg-slate-100 text-white dark:text-slate-900 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
          >
            {isVerifying ? 'Signing in...' : authRequired ? 'Sign in' : 'Continue'}
          </button>
        </form>
      </div>

      {/* Clean bottom spacer */}
      <div />
    </div>
  );
}
