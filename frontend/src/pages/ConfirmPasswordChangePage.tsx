import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { confirmPasswordChange } from '../services/authService';

const ConfirmPasswordChangePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  // Derive initial state from token presence — avoids synchronous setState
  // inside useEffect which triggers the react-hooks/set-state-in-effect rule.
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    token ? 'loading' : 'error',
  );
  const [message, setMessage] = useState(
    token ? '' : 'Missing confirmation token. Please use the link from your email.',
  );

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
            err instanceof Error ? err.message : 'Failed to confirm password change',
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
        <h1>Password Change</h1>

        {status === 'loading' && (
          <div className="loading-spinner">Confirming your password change...</div>
        )}

        {status === 'success' && (
          <div className="auth-success-message">
            {message}{' '}
            <Link to="/login" style={{ fontWeight: 600 }}>
              Login now
            </Link>
          </div>
        )}

        {status === 'error' && <p className="auth-error">{message}</p>}

        <p className="auth-link">
          <Link to="/login">Back to Login</Link>
        </p>
      </div>
    </div>
  );
};

export default ConfirmPasswordChangePage;
