import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getSecurityAudit } from '../services/adminService';
import type { SecurityAuditUser } from '../services/adminService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

// ── IP Geolocation cache (avoids duplicate API calls) ─────────────────────
const geoCache = new Map<string, string>();

async function resolveIpLocation(ip: string): Promise<string> {
  if (!ip || ip === 'unknown' || ip === '127.0.0.1' || ip === '::1') {
    return 'Localhost';
  }
  const cached = geoCache.get(ip);
  if (cached) return cached;

  try {
    const res = await fetch(`https://ipapi.co/${ip}/json/`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    const location = [data.city, data.country_name].filter(Boolean).join(', ') || 'Unknown';
    geoCache.set(ip, location);
    return location;
  } catch {
    const fallback = 'Lookup failed';
    geoCache.set(ip, fallback);
    return fallback;
  }
}

// ── Security badge logic ──────────────────────────────────────────────────
type BadgeLevel = 'red' | 'yellow' | 'green';

interface SecurityBadge {
  level: BadgeLevel;
  label: string;
  reasons: string[];
}

function computeSecurityBadge(user: SecurityAuditUser): SecurityBadge {
  const reasons: string[] = [];
  let level: BadgeLevel = 'green';

  // RED: failed_login_attempts > 5 OR status is suspect/locked
  if (user.failed_login_attempts > 5) {
    reasons.push(`${user.failed_login_attempts} failed login attempts`);
    level = 'red';
  }
  if (user.status === 'suspect' || user.status === 'locked') {
    reasons.push(`Account status: ${user.status}`);
    level = 'red';
  }

  // YELLOW: password hasn't been changed for > 6 months
  if (user.last_password_change) {
    const lastChange = new Date(user.last_password_change);
    const sixMonthsAgo = new Date();
    sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
    if (lastChange < sixMonthsAgo) {
      reasons.push('Password not changed in 6+ months');
      if (level !== 'red') level = 'yellow';
    }
  } else {
    reasons.push('Password never changed since registration');
    if (level !== 'red') level = 'yellow';
  }

  const labels: Record<BadgeLevel, string> = {
    red: 'High Risk',
    yellow: 'Warning',
    green: 'Secure',
  };

  if (level === 'green') {
    reasons.push('No issues detected');
  }

  return { level, label: labels[level], reasons };
}

// ── Helper: time-ago formatter ────────────────────────────────────────────
function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths}mo ago`;
}

// ── Main Component ────────────────────────────────────────────────────────
const AdminSecurityAuditPage: React.FC = () => {
  const [users, setUsers] = useState<SecurityAuditUser[]>([]);
  const [locations, setLocations] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterLevel, setFilterLevel] = useState<'all' | BadgeLevel>('all');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getSecurityAudit();
      setUsers(data);

      // Resolve IP locations in parallel (deduplicated)
      const uniqueIps = [...new Set(data.map(u => u.last_login_ip).filter(Boolean))] as string[];
      const locationResults: Record<string, string> = {};
      await Promise.allSettled(
        uniqueIps.map(async (ip) => {
          locationResults[ip] = await resolveIpLocation(ip);
        })
      );
      setLocations(locationResults);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load security audit');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredUsers = filterLevel === 'all'
    ? users
    : users.filter(u => computeSecurityBadge(u).level === filterLevel);

  // Stats
  const stats = {
    total: users.length,
    red: users.filter(u => computeSecurityBadge(u).level === 'red').length,
    yellow: users.filter(u => computeSecurityBadge(u).level === 'yellow').length,
    green: users.filter(u => computeSecurityBadge(u).level === 'green').length,
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1>🛡️ User Security Audit</h1>
        <div className="admin-actions">
          <Link to="/admin/users" className="btn btn-secondary">👥 User Management</Link>
          <Link to="/admin/logs" className="btn btn-secondary">📋 Audit Logs</Link>
        </div>
      </div>

      {/* ── Summary Cards ──────────────────────────────────────────── */}
      <div className="dashboard-grid" style={{ marginTop: 0, marginBottom: '24px' }}>
        <div
          className="dashboard-metric-card"
          style={{ cursor: 'pointer', border: filterLevel === 'all' ? '2px solid #3498db' : undefined }}
          onClick={() => setFilterLevel('all')}
        >
          <div className="dashboard-metric-title">Total Users</div>
          <div className="dashboard-metric-value">{stats.total}</div>
        </div>
        <div
          className="dashboard-metric-card"
          style={{ cursor: 'pointer', borderLeft: '4px solid #e74c3c', border: filterLevel === 'red' ? '2px solid #e74c3c' : undefined }}
          onClick={() => setFilterLevel('red')}
        >
          <div className="dashboard-metric-title">🔴 High Risk</div>
          <div className="dashboard-metric-value" style={{ color: '#e74c3c' }}>{stats.red}</div>
        </div>
        <div
          className="dashboard-metric-card"
          style={{ cursor: 'pointer', borderLeft: '4px solid #f39c12', border: filterLevel === 'yellow' ? '2px solid #f39c12' : undefined }}
          onClick={() => setFilterLevel('yellow')}
        >
          <div className="dashboard-metric-title">🟡 Warning</div>
          <div className="dashboard-metric-value" style={{ color: '#f39c12' }}>{stats.yellow}</div>
        </div>
        <div
          className="dashboard-metric-card"
          style={{ cursor: 'pointer', borderLeft: '4px solid #27ae60', border: filterLevel === 'green' ? '2px solid #27ae60' : undefined }}
          onClick={() => setFilterLevel('green')}
        >
          <div className="dashboard-metric-title">🟢 Secure</div>
          <div className="dashboard-metric-value" style={{ color: '#27ae60' }}>{stats.green}</div>
        </div>
      </div>

      {/* ── Security Table ─────────────────────────────────────────── */}
      <div className="table-container">
        <table className="admin-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Last Login IP</th>
              <th>Location</th>
              <th>Last Activity</th>
              <th>Failed Attempts</th>
              <th>PW Changed</th>
              <th>Security Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map(user => {
              const badge = computeSecurityBadge(user);
              const ip = user.last_login_ip || '—';
              const location = user.last_login_ip ? (locations[user.last_login_ip] || 'Resolving…') : '—';

              return (
                <tr key={user.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{user.email}</div>
                    <div style={{ fontSize: '0.78rem', color: '#95a5a6' }}>
                      <span className={`role-badge role-${user.role}`} style={{ fontSize: '0.7rem', padding: '2px 8px' }}>
                        {user.role}
                      </span>
                    </div>
                  </td>
                  <td>
                    <code style={{ fontSize: '0.85rem', background: '#f4f4f4', padding: '2px 6px', borderRadius: '4px' }}>
                      {ip}
                    </code>
                  </td>
                  <td style={{ fontSize: '0.88rem' }}>
                    {location === 'Resolving…' ? (
                      <span style={{ color: '#bbb', fontStyle: 'italic' }}>Resolving…</span>
                    ) : (
                      <span>{location}</span>
                    )}
                  </td>
                  <td>
                    <span title={user.last_login_at || 'Never'}>
                      {timeAgo(user.last_login_at)}
                    </span>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    {user.failed_login_attempts > 0 ? (
                      <span style={{
                        display: 'inline-block',
                        background: user.failed_login_attempts > 5 ? '#fdecea' : '#fff8e1',
                        color: user.failed_login_attempts > 5 ? '#c62828' : '#f57f17',
                        fontWeight: 700,
                        padding: '2px 10px',
                        borderRadius: '12px',
                        fontSize: '0.85rem',
                      }}>
                        {user.failed_login_attempts}
                      </span>
                    ) : (
                      <span style={{ color: '#bbb' }}>0</span>
                    )}
                  </td>
                  <td>
                    <span title={user.last_password_change || 'Never'}>
                      {timeAgo(user.last_password_change)}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`security-badge security-${badge.level}`}
                      title={badge.reasons.join('\n')}
                    >
                      {badge.level === 'red' && '🔴 '}
                      {badge.level === 'yellow' && '🟡 '}
                      {badge.level === 'green' && '🟢 '}
                      {badge.label}
                    </span>
                    {badge.reasons.length > 0 && badge.level !== 'green' && (
                      <div style={{ fontSize: '0.75rem', color: '#888', marginTop: '2px', maxWidth: '180px' }}>
                        {badge.reasons[0]}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {filteredUsers.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                  No users match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AdminSecurityAuditPage;
