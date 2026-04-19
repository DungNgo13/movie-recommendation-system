import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword } from '../services/authService';

const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!email.trim()) {
      setError('Email is required.');
      return;
    }

    try {
      setSubmitting(true);
      const message = await forgotPassword(email.trim());
      setSuccess(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reset email');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>Forgot Password</h1>
        <p style={{ color: '#888', fontSize: '0.9rem', textAlign: 'center', marginBottom: '20px' }}>
          Enter your email address and we'll send you a link to reset your password.
        </p>

        {success && <div className="auth-success-message">{success}</div>}
        {error && <p className="auth-error">{error}</p>}

        <div className="auth-field">
          <label htmlFor="forgot-email">Email</label>
          <input
            id="forgot-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
          />
        </div>

        <button type="submit" className="btn btn--primary auth-submit" disabled={submitting}>
          {submitting ? 'Sending...' : 'Send Reset Link'}
        </button>

        <p className="auth-link">
          Remember your password? <Link to="/login">Login</Link>
        </p>
      </form>
    </div>
  );
};

export default ForgotPasswordPage;
