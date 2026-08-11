import React, { useState } from 'react';
import { requestPasswordChange } from '../services/authService';
import { useAuth } from '../hooks/useAuthHook';
import { isPasswordValid } from '../utils/passwordValidator';
import PasswordStrengthIndicator from './PasswordStrengthIndicator';
import { useTranslation } from 'react-i18next';

// ── Known backend error → i18n key mapping ────────────────────────────────────
// Small, profile-scoped mapping for stable backend error messages.
// Unknown errors fall through to raw message (existing behavior).
const KNOWN_API_ERRORS: Record<string, string> = {
  'Current password is incorrect.': 'profile.password.errors.currentPasswordIncorrect',
};

const ChangePasswordForm: React.FC = () => {
  const { user } = useAuth();
  const { t } = useTranslation(['auth']);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  /** Translate known API error messages; pass unknown ones through unchanged. */
  const translateApiError = (msg: string): string => {
    const key = KNOWN_API_ERRORS[msg];
    return key ? t(`auth:${key}`) : msg;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!currentPassword) {
      setError(t("auth:profile.password.validation.currentRequired"));
      return;
    }
    if (!isPasswordValid(newPassword, user?.email)) {
      setError(t("auth:profile.password.validation.complexityNotMet"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t("auth:profile.password.validation.mismatch"));
      return;
    }
    if (currentPassword === newPassword) {
      setError(t("auth:profile.password.validation.mustDiffer"));
      return;
    }

    try {
      setSubmitting(true);
      await requestPasswordChange(currentPassword, newPassword);
      setEmailSent(true);
    } catch (err) {
      const raw = err instanceof Error ? err.message : t("auth:profile.password.errors.requestFailed");
      setError(translateApiError(raw));
    } finally {
      setSubmitting(false);
    }
  };

  if (emailSent) {
    return (
      <div className="change-password-form" id="change-password-form">
        <h3>{t("auth:profile.changePassword")}</h3>
        <div className="email-sent-banner" id="email-sent-banner">
          <span className="email-sent-banner__icon">📧</span>
          <div>
            <strong>{t("auth:profile.password.confirmation.title")}</strong>
            <p>
              {t("auth:profile.password.confirmation.message")}
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
          {t("auth:profile.password.confirmation.startOver")}
        </button>
      </div>
    );
  }

  return (
    <div className="change-password-form" id="change-password-form">
      <h3>{t("auth:profile.changePassword")}</h3>
      <form onSubmit={handleSubmit}>
        {error && <p className="auth-error">{error}</p>}

        <div className="auth-field">
          <label htmlFor="current-password">{t("auth:profile.password.fields.currentPassword")}</label>
          <input
            id="current-password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder={t("auth:profile.password.placeholders.currentPassword")}
          />
        </div>

        <div className="auth-field">
          <label htmlFor="new-password">{t("auth:profile.password.fields.newPassword")}</label>
          <input
            id="new-password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder={t("auth:profile.password.placeholders.newPassword")}
          />
          <PasswordStrengthIndicator password={newPassword} email={user?.email} />
        </div>

        <div className="auth-field">
          <label htmlFor="confirm-new-password">{t("auth:profile.password.fields.confirmNewPassword")}</label>
          <input
            id="confirm-new-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder={t("auth:profile.password.placeholders.confirmNewPassword")}
          />
        </div>

        <button
          type="submit"
          className="btn btn--primary auth-submit"
          disabled={submitting}
        >
          {submitting ? t("auth:profile.password.sending") : t("auth:profile.changePassword")}
        </button>
      </form>
    </div>
  );
};

export default ChangePasswordForm;
