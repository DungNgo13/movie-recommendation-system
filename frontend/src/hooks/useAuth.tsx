import React, { useState, useEffect, useCallback } from 'react';
import { fetchCurrentUser, logoutUser, getToken } from '../services/authService';
import { AuthContext } from './AuthContext';
import type { AuthUser } from '../services/authService';

/**
 * AuthProvider — wraps the app and provides auth state to all children.
 *
 * This file exports ONLY the AuthProvider React component, satisfying
 * react-refresh/only-export-components.
 *
 * For the useAuth hook, import from './useAuthHook' (or the barrel
 * re-export in index.ts).
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const userData = await fetchCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const logout = useCallback(() => {
    logoutUser();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
