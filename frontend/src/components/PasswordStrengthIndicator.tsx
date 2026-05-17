import React from 'react';
import { validatePassword } from '../utils/passwordValidator';

interface PasswordStrengthIndicatorProps {
  password: string;
  email?: string;
}

const PasswordStrengthIndicator: React.FC<PasswordStrengthIndicatorProps> = ({
  password,
  email,
}) => {
  if (!password) return null;

  const requirements = validatePassword(password, email);
  const metCount = requirements.filter((r) => r.met).length;
  const totalCount = requirements.length;
  const strengthPercent = totalCount > 0 ? (metCount / totalCount) * 100 : 0;

  let strengthLabel = 'Weak';
  let strengthColor = '#e74c3c';
  if (strengthPercent >= 100) {
    strengthLabel = 'Strong';
    strengthColor = '#27ae60';
  } else if (strengthPercent >= 60) {
    strengthLabel = 'Medium';
    strengthColor = '#f39c12';
  }

  return (
    <div className="password-strength" id="password-strength-indicator">
      {/* Strength bar */}
      <div className="password-strength-bar">
        <div
          className="password-strength-bar__fill"
          style={{ width: `${strengthPercent}%`, backgroundColor: strengthColor }}
        />
      </div>
      <span className="password-strength-label" style={{ color: strengthColor }}>
        {strengthLabel}
      </span>

      {/* Requirements checklist */}
      <ul className="password-requirements">
        {requirements.map((req, i) => (
          <li
            key={i}
            className={`password-req ${req.met ? 'password-req--met' : 'password-req--unmet'}`}
          >
            <span className="password-req__icon">{req.met ? '✓' : '✗'}</span>
            {req.label}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default PasswordStrengthIndicator;
