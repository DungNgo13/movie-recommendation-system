import { useContext } from 'react';
import { ThemeContext } from '../theme/ThemeContext';
import type { ThemeContextValue } from '../theme/ThemeContext';

/**
 * Access the current theme mode, resolved theme, and setter.
 * Must be used inside `<ThemeProvider>`.
 */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within a <ThemeProvider>');
  }
  return ctx;
}
