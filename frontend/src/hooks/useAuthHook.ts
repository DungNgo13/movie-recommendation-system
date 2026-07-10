import { useContext } from 'react';
import { AuthContext } from './AuthContext';
import type { AuthContextType } from './AuthContext';

/**
 * Hook to access the current auth state (user, loading, refreshUser, logout).
 *
 * Separated from AuthProvider to satisfy react-refresh/only-export-components:
 * useAuth.tsx exports only the AuthProvider component, while this file
 * exports the hook.
 */
export const useAuth = (): AuthContextType => {
  return useContext(AuthContext);
};
