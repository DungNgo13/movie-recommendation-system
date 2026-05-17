import React, { useState } from 'react';
import { requestPasswordChange } from '../services/authService';
import { useAuth } from '../hooks/useAuth';
import { isPasswordValid } from '../utils/passwordValidator';
import PasswordStrengthIndicator from './PasswordStrengthIndicator';

const ChangePasswordForm: React.FC = () => {
  const { user } = useAuth();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!currentPassword) {
      setError('Current password is required.');
      return;
    }
    if (!isPasswordValid(newPassword, user?.email)) {
      setError('New password does not meet the complexity requirements.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    if (currentPassword === newPassword) {
      setError('New password must be different from the current password.');
      return;
    }

    try {
      setSubmitting(true);
      await requestPasswordChange(currentPassword, newPassword);
      setEmailSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request password change');
    } finally {
      setSubmitting(false);
    }
  };

  if (emailSent) {
    return (
      <div className="change-password-form" id="change-password-form">
        <h3>Change Password</h3>
        <div className="email-sent-banner" id="email-sent-banner">
          <span className="email-sent-banner__icon">📧</span>
          <div>
            <strong>Confirmation email sent!</strong>
            <p>
              Please check your inbox and click the confirmation link to complete
              the password change. The link expires in 15 minutes.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => {
            setEmailSent(false);
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
          }}
        >
          Start Over
        </button>
      </div>
    );
  }

  return (
    <div className="change-password-form" id="change-password-form">
      <h3>Change Password</h3>
      <form onSubmit={handleSubmit}>
        {error && <p className="auth-error">{error}</p>}

        <div className="auth-field">
          <label htmlFor="current-password">Current Password</label>
          <input
            id="current-password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Enter your current password"
          />
        </div>

        <div className="auth-field">
          <label htmlFor="new-password">New Password</label>
          <input
            id="new-password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Enter a strong new password"
          />
          <PasswordStrengthIndicator password={newPassword} email={user?.email} />
        </div>

        <div className="auth-field">
          <label htmlFor="confirm-new-password">Confirm New Password</label>
          <input
            id="confirm-new-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Repeat new password"
          />
        </div>

        <button
          type="submit"
          className="btn btn--primary auth-submit"
          disabled={submitting}
        >
          {submitting ? 'Sending...' : 'Change Password'}
        </button>
      </form>
    </div>
  );
};

export default ChangePasswordForm;
