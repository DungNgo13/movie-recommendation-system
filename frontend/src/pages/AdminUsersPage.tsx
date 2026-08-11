import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { AuthUser } from '../services/authService';
import { getAdminUsers, updateAdminUserRole, forceResetUserPassword } from '../services/adminService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const AdminUsersPage: React.FC = () => {
  const { t } = useTranslation(['admin', 'common']);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reset password modal state
  const [resetTarget, setResetTarget] = useState<AuthUser | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);
  const [resetSubmitting, setResetSubmitting] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getAdminUsers();
      setUsers(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve users';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, currentRole: 'admin' | 'user') => {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    const newRoleLabel = newRole === 'admin' ? t("admin:users.roleAdmin") : t("admin:users.roleUser");
    if (!window.confirm(t("admin:users.confirmRoleChange", { role: newRoleLabel }))) {
      return;
    }

    try {
      const updatedUser = await updateAdminUserRole(userId, newRole);
      setUsers(users.map(u => u.id === userId ? updatedUser : u));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update user role';
      alert(msg);
    }
  };

  const openResetModal = (user: AuthUser) => {
    setResetTarget(user);
    setResetPassword('');
    setResetConfirm('');
    setResetError(null);
    setResetSuccess(null);
  };

  const closeResetModal = () => {
    setResetTarget(null);
    setResetPassword('');
    setResetConfirm('');
    setResetError(null);
    setResetSuccess(null);
  };

  const handleForceReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    setResetSuccess(null);

    if (!resetPassword || resetPassword.length < 6) {
      setResetError(t("admin:users.errorPwLength"));
      return;
    }
    if (resetPassword !== resetConfirm) {
      setResetError(t("admin:users.errorPwMismatch"));
      return;
    }
    if (!resetTarget) return;

    try {
      setResetSubmitting(true);
      const message = await forceResetUserPassword(resetTarget.id, resetPassword);
      setResetSuccess(message);
      setResetPassword('');
      setResetConfirm('');
    } catch (err) {
      setResetError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setResetSubmitting(false);
    }
  };

  /** Localize role display value */
  const displayRole = (role: string) => {
    if (role === 'admin') return t("admin:users.roleAdmin");
    if (role === 'user') return t("admin:users.roleUser");
    return role;
  };

  /** Localize status display value */
  const displayStatus = (status: string) => {
    if (status === 'active') return t("admin:users.statusActive");
    return status;
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1>{t("admin:users.title")}</h1>
        <div className="admin-actions">
          <Link to="/admin/movies" className="btn btn-secondary">
            {t("admin:users.manageMovies")}
          </Link>
        </div>
      </div>
      
      <div className="table-container">
        <table className="admin-table">
          <thead>
            <tr>
              <th>{t("admin:users.id")}</th>
              <th>{t("admin:users.email")}</th>
              <th>{t("admin:users.role")}</th>
              <th>{t("admin:users.status")}</th>
              <th>{t("admin:users.createdAt")}</th>
              <th>{t("admin:users.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.id}>
                <td className="truncate-id" title={user.id}>{user.id.substring(0, 8)}...</td>
                <td>{user.email}</td>
                <td>
                  <span className={`role-badge role-${user.role}`}>
                    {displayRole(user.role)}
                  </span>
                </td>
                <td>
                  <span className={`role-badge status-${(user as unknown as Record<string, unknown>).status || 'active'}`}>
                    {displayStatus(((user as unknown as Record<string, unknown>).status as string) || 'active')}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td className="actions-cell">
                  <button
                    className={`btn ${user.role === 'admin' ? 'btn-danger' : 'btn-primary'}`}
                    onClick={() => handleRoleChange(user.id, user.role)}
                  >
                    {user.role === 'admin' ? t("admin:users.makeUser") : t("admin:users.makeAdmin")}
                  </button>
                  <button
                    className="btn btn--edit"
                    onClick={() => openResetModal(user)}
                    title={t("admin:users.resetPwTooltip")}
                  >
                    🔑 {t("admin:users.resetPw")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Reset Password Modal */}
      {resetTarget && (
        <div className="confirm-overlay" onClick={(e) => { if (e.target === e.currentTarget) closeResetModal(); }}>
          <div className="confirm-dialog">
            <h3>🔑 {t("admin:users.resetPassword")}</h3>
            <p style={{ color: '#555', marginBottom: '16px' }}>
              {t("admin:users.resetPrompt")} <strong>{resetTarget.email}</strong>.
            </p>

            {resetSuccess && <div className="auth-success-message">{resetSuccess}</div>}
            {resetError && <p className="auth-error">{resetError}</p>}

            {!resetSuccess ? (
              <form onSubmit={handleForceReset}>
                <div className="admin-form-group">
                  <label htmlFor="admin-reset-pw">{t("admin:users.newPassword")}</label>
                  <input
                    id="admin-reset-pw"
                    type="password"
                    value={resetPassword}
                    onChange={(e) => setResetPassword(e.target.value)}
                    placeholder={t("admin:users.pwMinLength")}
                  />
                </div>
                <div className="admin-form-group">
                  <label htmlFor="admin-reset-confirm">{t("admin:users.confirmPassword")}</label>
                  <input
                    id="admin-reset-confirm"
                    type="password"
                    value={resetConfirm}
                    onChange={(e) => setResetConfirm(e.target.value)}
                    placeholder={t("admin:users.pwRepeat")}
                  />
                </div>
                <div className="confirm-actions">
                  <button type="button" className="btn btn--secondary" onClick={closeResetModal}>
                    {t("admin:users.cancel")}
                  </button>
                  <button type="submit" className="btn btn--primary" disabled={resetSubmitting}>
                    {resetSubmitting ? t("admin:users.resetting") : t("admin:users.resetPassword")}
                  </button>
                </div>
              </form>
            ) : (
              <div className="confirm-actions">
                <button className="btn btn--primary" onClick={closeResetModal}>
                  {t("admin:users.done")}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminUsersPage;
