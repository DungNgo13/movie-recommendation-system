import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { AuthUser } from '../services/authService';
import { getAdminUsers, updateAdminUserRole } from '../services/adminService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const AdminUsersPage: React.FC = () => {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
                <td>{new Date(user.created_at).toLocaleDateString()}</td>
                <td className="actions-cell">
                  <button
                    className={`btn ${user.role === 'admin' ? 'btn-danger' : 'btn-primary'}`}
                    onClick={() => handleRoleChange(user.id, user.role)}
                  >
                    Make {user.role === 'admin' ? 'User' : 'Admin'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AdminUsersPage;
