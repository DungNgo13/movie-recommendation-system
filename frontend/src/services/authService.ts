import { API_BASE_URL } from '../config';

const TOKEN_KEY = 'auth_token';

export interface AuthUser {
  id: string;
  email: string;
  role: 'admin' | 'user';
  status: string;
  created_at: string;
  last_login_at?: string | null;
}

export interface GuestWatchEntryPayload {
  movie_id: string;
  current_time_seconds: number;
  duration_seconds: number;
  progress_percent: number;
}

export interface LoginData {
  email: string;
  password: string;
  guest_history?: GuestWatchEntryPayload[];
}

export interface RegisterData {
  email: string;
  password: string;
}

export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
};

export const registerUser = async (data: RegisterData): Promise<AuthUser> => {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || 'Registration failed');
  }
  return response.json();
};

export const loginUser = async (data: LoginData): Promise<string> => {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || 'Login failed');
  }
  const result = await response.json();
  const token = result.access_token as string;
  setToken(token);
  return token;
};

export const fetchCurrentUser = async (): Promise<AuthUser> => {
  const token = getToken();
  if (!token) {
    throw new Error('No token');
  }
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    removeToken();
    throw new Error('Not authenticated');
  }
  return response.json();
};

export const logoutUser = (): void => {
  removeToken();
};

export const forgotPassword = async (email: string): Promise<string> => {
  const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || 'Failed to send reset email');
  }
  const data = await response.json();
  return data.message;
};

export const resetPassword = async (token: string, newPassword: string): Promise<string> => {
  const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || 'Failed to reset password');
  }
  const data = await response.json();
  return data.message;
};

/**
 * Sliding Session — exchange the current valid JWT for a fresh one.
 * Called silently in the background; never triggers a page reload.
 * Returns the new token string, or null if the refresh fails (token already expired).
 */
export const refreshToken = async (): Promise<string | null> => {
  const currentToken = getToken();
  if (!currentToken) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    if (!response.ok) return null;
    const data = await response.json();
    const newToken = data.access_token as string;
    setToken(newToken);
    return newToken;
  } catch {
    return null; // network error — don't disrupt the user
  }
};
