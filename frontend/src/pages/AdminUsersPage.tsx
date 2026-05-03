import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { AuthUser } from '../services/authService';
import { getAdminUsers, updateAdminUserRole, forceResetUserPassword } from '../services/adminService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const AdminUsersPage: React.FC = () => {
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
    if (!window.confirm(`Are you sure you want to change this user's role to ${newRole}?`)) {
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
      setResetError('Password must be at least 6 characters.');
      return;
    }
    if (resetPassword !== resetConfirm) {
      setResetError('Passwords do not match.');
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

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1>User Management</h1>
        <div className="admin-actions">
          <Link to="/admin/movies" className="btn btn-secondary">
            Manage Movies
          </Link>
        </div>
      </div>
      
      <div className="table-container">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created At</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.id}>
                <td className="truncate-id" title={user.id}>{user.id.substring(0, 8)}...</td>
                <td>{user.email}</td>
                <td>
                  <span className={`role-badge role-${user.role}`}>
                    {user.role}
                  </span>
                </td>
                <td>
                  <span className={`role-badge status-${(user as unknown as Record<string, unknown>).status || 'active'}`}>
                    {((user as unknown as Record<string, unknown>).status as string) || 'active'}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td className="actions-cell">
                  <button
                    className={`btn ${user.role === 'admin' ? 'btn-danger' : 'btn-primary'}`}
                    onClick={() => handleRoleChange(user.id, user.role)}
                  >
                    Make {user.role === 'admin' ? 'User' : 'Admin'}
                  </button>
                  <button
                    className="btn btn--edit"
                    onClick={() => openResetModal(user)}
                    title="Reset this user's password"
                  >
                    🔑 Reset PW
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
            <h3>🔑 Reset Password</h3>
            <p style={{ color: '#555', marginBottom: '16px' }}>
              Set a new temporary password for <strong>{resetTarget.email}</strong>.
            </p>

            {resetSuccess && <div className="auth-success-message">{resetSuccess}</div>}
            {resetError && <p className="auth-error">{resetError}</p>}

            {!resetSuccess ? (
              <form onSubmit={handleForceReset}>
                <div className="admin-form-group">
                  <label htmlFor="admin-reset-pw">New Password</label>
                  <input
                    id="admin-reset-pw"
                    type="password"
                    value={resetPassword}
                    onChange={(e) => setResetPassword(e.target.value)}
                    placeholder="At least 6 characters"
                  />
                </div>
                <div className="admin-form-group">
                  <label htmlFor="admin-reset-confirm">Confirm Password</label>
                  <input
                    id="admin-reset-confirm"
                    type="password"
                    value={resetConfirm}
                    onChange={(e) => setResetConfirm(e.target.value)}
                    placeholder="Repeat password"
                  />
                </div>
                <div className="confirm-actions">
                  <button type="button" className="btn btn--secondary" onClick={closeResetModal}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn--primary" disabled={resetSubmitting}>
                    {resetSubmitting ? 'Resetting...' : 'Reset Password'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="confirm-actions">
                <button className="btn btn--primary" onClick={closeResetModal}>
                  Done
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
