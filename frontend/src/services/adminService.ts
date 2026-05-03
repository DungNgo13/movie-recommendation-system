import { getToken } from './authService';
import type { AuthUser } from './authService';

import { API_BASE_URL } from '../config';

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  } : {
    'Content-Type': 'application/json',
  };
}

export interface AdminDashboardData {
  total_movies: number;
  total_users: number;
  total_admins: number;
  total_favorites: number;
  total_ratings: number;
  total_watch_history: number;
}

export interface AdminAuditLog {
  id: string;
  admin_user_email: string;
  action_type: string;
  target_type: string;
  target_id: string | null;
  description: string | null;
  created_at: string;
}

export const getDashboardMetrics = async (): Promise<AdminDashboardData> => {
  const response = await fetch(`${API_BASE_URL}/admin/dashboard`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error('Failed to fetch dashboard metrics');
  return response.json();
};

export const getAuditLogs = async (): Promise<AdminAuditLog[]> => {
  const response = await fetch(`${API_BASE_URL}/admin/logs`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error('Failed to fetch audit logs');
  return response.json();
};

export const getAdminUsers = async (): Promise<AuthUser[]> => {
  const response = await fetch(`${API_BASE_URL}/admin/users`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error('Failed to fetch users');
  }
  return response.json();
};

export const updateAdminUserRole = async (userId: string, targetRole: 'admin' | 'user'): Promise<AuthUser> => {
  const response = await fetch(`${API_BASE_URL}/admin/users/${userId}/role`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ role: targetRole }),
  });
  
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || 'Failed to update user role');
  }
  return response.json();
};

export const forceResetUserPassword = async (userId: string, newPassword: string): Promise<string> => {
  const response = await fetch(`${API_BASE_URL}/admin/users/${userId}/force-reset-password`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ new_password: newPassword }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || 'Failed to reset password');
  }
  const result = await response.json();
  return result.message;
};

export interface SecurityAuditUser {
  id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
  last_login_ip: string | null;
  last_login_at: string | null;
  last_password_change: string | null;
  last_email_change: string | null;
  failed_login_attempts: number;
}

export const getSecurityAudit = async (): Promise<SecurityAuditUser[]> => {
  const response = await fetch(`${API_BASE_URL}/admin/users/security-audit`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error('Failed to fetch security audit data');
  return response.json();
};

