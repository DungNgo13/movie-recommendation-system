import React, { useState, useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { confirmPasswordChange } from '../services/authService';
import { useTranslation } from 'react-i18next';

const ConfirmPasswordChangePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  // Derive initial state from token presence — avoids synchronous setState
  // inside useEffect which triggers the react-hooks/set-state-in-effect rule.
  const { t } = useTranslation(['auth']);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    token ? 'loading' : 'error',
  );
  const [message, setMessage] = useState(
    token ? '' : t("auth:confirmPasswordChange.missingToken", "Missing confirmation token. Please use the link from your email."),
  );

  // Stable ref for t — avoids re-running the confirmation API on language change
  const tRef = useRef(t);
  useEffect(() => { tRef.current = t; });

  useEffect(() => {
    // If there's no token, the initial state already shows the error.
    if (!token) return;

    let cancelled = false;

    const confirm = async () => {
      try {
        const result = await confirmPasswordChange(token);
        if (!cancelled) {
          setStatus('success');
          setMessage(result);
        }
      } catch (err) {
        if (!cancelled) {
          setStatus('error');
          setMessage(
            err instanceof Error ? err.message : tRef.current("auth:confirmPasswordChange.error", "Failed to confirm password change"),
          );
        }
      }
    };

    confirm();

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="auth-page">
      <div className="auth-form" id="confirm-password-change">
        <h1>{t("auth:confirmPasswordChange.title", "Password Change")}</h1>

        {status === 'loading' && (
          <div className="loading-spinner">{t("auth:confirmPasswordChange.loading", "Confirming your password change...")}</div>
        )}

        {status === 'success' && (
          <div className="auth-success-message">
            {message}{' '}
            <Link to="/login" style={{ fontWeight: 600 }}>
              {t("auth:confirmPasswordChange.loginNow", "Login now")}
            </Link>
          </div>
        )}

        {status === 'error' && <p className="auth-error">{message}</p>}

        <p className="auth-link">
          <Link to="/login">{t("auth:confirmPasswordChange.backToLogin", "Back to Login")}</Link>
        </p>
      </div>
    </div>
  );
};

export default ConfirmPasswordChangePage;
