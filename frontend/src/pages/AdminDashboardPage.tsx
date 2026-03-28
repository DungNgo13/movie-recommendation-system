import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getDashboardMetrics } from '../services/adminService';
import type { AdminDashboardData } from '../services/adminService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const AdminDashboardPage: React.FC = () => {
  const [metrics, setMetrics] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getDashboardMetrics();
      setMetrics(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve metrics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;
  if (!metrics) return null;

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1>Admin Dashboard</h1>
        <div className="admin-actions">
          <Link to="/admin/movies" className="btn btn-secondary">Manage Movies</Link>
          <Link to="/admin/users" className="btn btn-secondary">Manage Users</Link>
          <Link to="/admin/logs" className="btn btn-secondary">Audit Logs</Link>
        </div>
      </div>
      
      <div className="dashboard-grid">
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-title">Total Movies</span>
          <span className="dashboard-metric-value">{metrics.total_movies}</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-title">Total Users</span>
          <span className="dashboard-metric-value">{metrics.total_users}</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-title">Admins</span>
          <span className="dashboard-metric-value">{metrics.total_admins}</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-title">User Favorites</span>
          <span className="dashboard-metric-value">{metrics.total_favorites}</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-title">User Ratings</span>
          <span className="dashboard-metric-value">{metrics.total_ratings}</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-title">Watch History</span>
          <span className="dashboard-metric-value">{metrics.total_watch_history}</span>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboardPage;
