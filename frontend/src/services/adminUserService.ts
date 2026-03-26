import { getToken } from './authService';
import type { AuthUser } from './authService';

const API_BASE_URL = 'http://localhost:8000/api/v1';

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  } : {};
}

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
