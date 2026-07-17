import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { loginUser } from '../services/authService';
import { getGuestWatchHistory, clearGuestWatchHistory } from '../services/continueWatchingService';
import { getGuestFavoriteIds, mergeGuestFavorites, clearGuestFavorites } from '../services/favoriteService';
import { useAuth } from '../hooks/useAuthHook';
import { useTranslation } from 'react-i18next';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { refreshUser } = useAuth();
  const { t } = useTranslation(['auth', 'common']);
  
  const successMessage = location.state?.message;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError('Email is required.');
      return;
    }
    if (!password) {
      setError('Password is required.');
      return;
    }

    try {
      setSubmitting(true);

      // Grab guest watch history from localStorage for cold-start merge.
      // getGuestWatchHistory() auto-migrates old entries to canonical schema.
      // Map to backend's expected field names before sending.
      const guestHistory = getGuestWatchHistory().map((entry) => ({
        movie_id: entry.movie_id,
        current_time_seconds: entry.playback_position_seconds,
        duration_seconds: entry.duration_seconds,
        progress_percent: entry.progress_percent,
      }));

      await loginUser({
        email: email.trim(),
        password,
        ...(guestHistory.length > 0 ? { guest_history: guestHistory } : {}),
      });

      // Merge succeeded with login — clear guest watch data
      clearGuestWatchHistory();

      // Merge guest favorites into the authenticated account (non-blocking)
      const guestFavIds = getGuestFavoriteIds();
      if (guestFavIds.length > 0) {
        try {
          await mergeGuestFavorites(guestFavIds);
          clearGuestFavorites();
        } catch {
          // Non-fatal: guest favorites stay in localStorage for next login attempt
        }
      }

      await refreshUser();
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>{t("auth:login.title", "Login")}</h1>

        {successMessage && <div className="auth-success-message">{successMessage}</div>}
        {error && <p className="auth-error">{error}</p>}

        <div className="auth-field">
          <label htmlFor="login-email">{t("auth:login.email", "Email")}</label>
          <input
            id="login-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
          />
        </div>

        <div className="auth-field">
          <label htmlFor="login-password">{t("auth:login.password", "Password")}</label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••"
          />
        </div>

        <button type="submit" className="btn btn--primary" disabled={submitting}>
          {submitting ? t("common:loading", "Loading...") : t("auth:login.submit", "Sign In")}
        </button>

        <p className="auth-switch">
          {t("auth:login.registerPrompt", "Don't have an account?")}{' '}
          <Link to="/register">{t("auth:login.registerLink", "Sign up")}</Link>
        </p>
        
        <p className="auth-forgot-password">
          <Link to="/forgot-password">{t("auth:login.forgotPassword", "Forgot password?")}</Link>
        </p>
      </form>
    </div>
  );
};

export default LoginPage;
