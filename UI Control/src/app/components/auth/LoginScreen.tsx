import React, { useEffect, useId, useRef, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import homecartelLogo from '@/assets/homecartel_logo.png';
import loginRoom from '@/assets/login-room.jpg';

export type AuthMode = 'accounts' | 'pin' | 'open';

export interface AuthUser {
  email: string;
  role: string;
}

export interface LoginResult {
  /** Set after an email + password login (server session cookie). */
  user?: AuthUser;
  /** Set after a PIN login (legacy mode, used until the first account exists). */
  pin?: string;
}

interface LoginScreenProps {
  mode: AuthMode;
  onLoginSuccess: (result: LoginResult) => void;
  isLoadingConfig?: boolean;
}

const ADMIN_EMAIL = 'homecartelmarketingclaude@gmail.com';
const REQUEST_ACCESS_HREF = `mailto:${ADMIN_EMAIL}?subject=${encodeURIComponent('HomeCartel Studio access request')}`;
const RESET_HREF = `mailto:${ADMIN_EMAIL}?subject=${encodeURIComponent('HomeCartel Studio password reset')}`;

export function LoginScreen({ mode, onLoginSuccess, isLoadingConfig = false }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const errorId = useId();
  const resetId = useId();

  const usesEmail = mode === 'accounts';
  const usesPassword = mode !== 'open';

  useEffect(() => {
    // Don't pop the on-screen keyboard on touch devices.
    if (!isLoadingConfig && window.matchMedia('(pointer: fine)').matches) {
      firstFieldRef.current?.focus();
    }
  }, [isLoadingConfig, mode]);

  const clearError = () => {
    if (error) setError(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (mode === 'open') {
      onLoginSuccess({});
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === 'accounts') {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim(), password }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.ok && data.user) {
          onLoginSuccess({ user: data.user });
        } else {
          setError(data.error || 'Could not log in. Please try again.');
          setPassword('');
        }
      } else {
        const candidate = password.trim();
        const res = await fetch('/api/auth/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pin: candidate }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.valid) {
          onLoginSuccess({ pin: candidate });
        } else {
          setError(data.error || 'Incorrect PIN. Please try again.');
          setPassword('');
        }
      }
    } catch {
      setError('Could not connect to the server.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const passwordLabel = mode === 'pin' ? 'Studio PIN' : 'Password';

  return (
    <main className="hc-login">
      <div className="hc-login__card">
        <section className="hc-login__panel" aria-labelledby="hc-login-title">
          <img src={homecartelLogo} alt="HomeCartel" className="hc-login__logo" />
          <h1 id="hc-login-title" className="hc-login__title">
            Log In To Your Account
          </h1>
          <p className="hc-login__intro">
            {mode === 'open'
              ? 'This Studio is open access. Continue to start creating content.'
              : 'Sign in to the Marketing Studio to run pipelines, check rows, and manage your content queue.'}
          </p>

          {isLoadingConfig ? (
            <div className="hc-login__skeleton" role="status" aria-label="Loading" />
          ) : (
            <form onSubmit={handleSubmit} aria-describedby={error ? errorId : undefined}>
              {usesEmail && (
                <div className="hc-login__field">
                  <label htmlFor="email" className="hc-login__label">
                    Email <span aria-hidden="true">*</span>
                  </label>
                  <input
                    ref={firstFieldRef}
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    spellCheck={false}
                    enterKeyHint="next"
                    required
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      clearError();
                    }}
                    placeholder="you@homecartel.net"
                    disabled={isSubmitting}
                    aria-invalid={error ? true : undefined}
                    className="hc-login__input"
                  />
                </div>
              )}

              {usesPassword && (
                <div className="hc-login__field">
                  <label htmlFor="current-password" className="hc-login__label">
                    {passwordLabel} <span aria-hidden="true">*</span>
                  </label>
                  <div className="hc-login__input-wrap">
                    <input
                      ref={usesEmail ? undefined : firstFieldRef}
                      id="current-password"
                      name={mode === 'pin' ? 'pin' : 'password'}
                      type={showPassword ? 'text' : 'password'}
                      autoComplete={mode === 'pin' ? 'off' : 'current-password'}
                      inputMode={mode === 'pin' ? 'numeric' : undefined}
                      spellCheck={false}
                      enterKeyHint="done"
                      required
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        clearError();
                      }}
                      placeholder={mode === 'pin' ? 'Enter your PIN' : 'Enter your password'}
                      disabled={isSubmitting}
                      aria-invalid={error ? true : undefined}
                      className="hc-login__input hc-login__input--with-toggle"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? `Hide ${passwordLabel.toLowerCase()}` : `Show ${passwordLabel.toLowerCase()}`}
                      aria-pressed={showPassword}
                      className="hc-login__toggle"
                    >
                      {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                    </button>
                  </div>
                </div>
              )}

              {mode === 'accounts' && (
                <>
                  <button
                    type="button"
                    className="hc-login__link"
                    aria-expanded={showReset}
                    aria-controls={resetId}
                    onClick={() => setShowReset((v) => !v)}
                  >
                    Forgot Password
                  </button>
                  <div id={resetId} hidden={!showReset}>
                    <p className="hc-login__notice">
                      Passwords are reset by your Studio admin.{' '}
                      <a className="hc-login__link" href={RESET_HREF}>
                        Email {ADMIN_EMAIL}
                      </a>{' '}
                      and we'll set a new one.
                    </p>
                  </div>
                </>
              )}

              <div id={errorId} role="alert">
                {error && <p className="hc-login__error">{error}</p>}
              </div>

              <button type="submit" disabled={isSubmitting} className="hc-login__submit">
                {isSubmitting ? 'Logging in…' : mode === 'open' ? 'Continue' : 'Log In'}
              </button>

              {mode === 'accounts' && (
                <p className="hc-login__foot">
                  Don't have an account?{' '}
                  <a className="hc-login__link" href={REQUEST_ACCESS_HREF}>
                    Sign Up
                  </a>
                </p>
              )}
            </form>
          )}
        </section>

        <div
          className="hc-login__photo"
          role="presentation"
          style={{ backgroundImage: `url(${loginRoom})` }}
        />
      </div>
    </main>
  );
}
