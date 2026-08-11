import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getAuditLogs } from '../services/adminService';
import type { AdminAuditLog } from '../services/adminService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const AdminAuditLogsPage: React.FC = () => {
  const { t } = useTranslation(['admin', 'common']);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getAuditLogs();
      setLogs(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve audit logs';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1>{t("admin:auditLogs.title")}</h1>
        <div className="admin-actions">
          <Link to="/admin" className="btn btn-secondary">{t("admin:auditLogs.dashboard")}</Link>
        </div>
      </div>
      
      <div className="table-container">
        <table className="admin-table">
          <thead>
            <tr>
              <th>{t("admin:auditLogs.date")}</th>
              <th>{t("admin:auditLogs.adminEmail")}</th>
              <th>{t("admin:auditLogs.action")}</th>
              <th>{t("admin:auditLogs.target")}</th>
              <th>{t("admin:auditLogs.description")}</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={5} className="no-results" style={{ textAlign: "center" }}>{t("admin:auditLogs.noLogs")}</td>
              </tr>
            ) : logs.map(log => (
              <tr key={log.id}>
                <td style={{ whiteSpace: "nowrap" }}>{new Date(log.created_at).toLocaleString()}</td>
                <td>{log.admin_user_email}</td>
                <td>
                  <span className={`role-badge role-${log.action_type.includes('delete') ? 'admin' : 'user'}`}>
                    {log.action_type}
                  </span>
                </td>
                <td>{log.target_type}</td>
                <td>{log.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AdminAuditLogsPage;
