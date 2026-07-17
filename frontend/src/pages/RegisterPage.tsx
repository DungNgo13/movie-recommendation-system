import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { registerUser, removeToken } from '../services/authService';
import { isPasswordValid } from '../utils/passwordValidator';
import PasswordStrengthIndicator from '../components/PasswordStrengthIndicator';
import { useTranslation } from 'react-i18next';
// useAuth hook not needed here anymore

const RegisterPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const { t } = useTranslation(['auth', 'common']);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError('Email is required.');
      return;
    }
    if (!password || !isPasswordValid(password, email)) {
      setError('Password does not meet the complexity requirements.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    try {
      setSubmitting(true);
      await registerUser({ email: email.trim(), password });
      removeToken(); // Explicitly remove any tokens
      navigate('/login', { state: { message: 'Registration successful. Please log in.' } });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>{t("auth:register.title", "Register")}</h1>

        {error && <p className="auth-error">{error}</p>}

        <div className="auth-field">
          <label htmlFor="register-email">{t("auth:register.email", "Email")}</label>
          <input
            id="register-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
          />
        </div>

        <div className="auth-field">
          <label htmlFor="register-password">{t("auth:register.password", "Password")}</label>
          <input
            id="register-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Min 8 chars, uppercase, number, special"
          />
          <PasswordStrengthIndicator password={password} email={email} />
        </div>

        <div className="auth-field">
          <label htmlFor="register-confirm">{t("auth:register.confirmPassword", "Confirm Password")}</label>
          <input
            id="register-confirm"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Repeat password"
          />
        </div>

        <button type="submit" className="btn btn--primary auth-submit" disabled={submitting}>
          {submitting ? t("common:loading", "Creating account...") : t("auth:register.submit", "Register")}
        </button>

        <p className="auth-link">
          {t("auth:register.loginPrompt", "Already have an account?")} <Link to="/login">{t("auth:register.loginLink", "Sign in")}</Link>
        </p>
      </form>
    </div>
  );
};

export default RegisterPage;
