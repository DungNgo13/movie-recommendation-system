import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { resetPassword } from '../services/authService';

const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!token) {
      setError('Missing reset token. Please use the link from your email.');
      return;
    }
    if (!newPassword || newPassword.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    try {
      setSubmitting(true);
      const message = await resetPassword(token, newPassword);
      setSuccess(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Reset Password</h1>
        <p style={{ color: '#888', fontSize: '0.9rem', textAlign: 'center', marginBottom: '20px' }}>
          Enter your new password below.
        </p>

        {success && (
          <div className="auth-success-message">
            {success} <Link to="/login" style={{ fontWeight: 600 }}>Login now →</Link>
          </div>
        )}
        {error && <p className="auth-error">{error}</p>}

        {!success && (
          <>
            <div className="auth-field">
              <label htmlFor="reset-password">New Password</label>
              <input
                id="reset-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 6 characters"
              />
            </div>

            <div className="auth-field">
              <label htmlFor="reset-confirm">Confirm Password</label>
              <input
                id="reset-confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat password"
              />
            </div>

            <button type="submit" className="btn btn--primary auth-submit" disabled={submitting}>
              {submitting ? 'Resetting...' : 'Reset Password'}
            </button>
          </>
        )}

        <p className="auth-link">
          <Link to="/login">← Back to Login</Link>
        </p>
      </form>
    </div>
  );
};

export default ResetPasswordPage;
