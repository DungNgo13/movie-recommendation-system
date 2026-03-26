const API_BASE_URL = 'http://localhost:8000/api/v1';

const TOKEN_KEY = 'auth_token';

export interface AuthUser {
  id: string;
  email: string;
  role: 'admin' | 'user';
  created_at: string;
}

export interface LoginData {
  email: string;
  password: string;
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
