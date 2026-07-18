import { useContext } from 'react';
import { ThemeContext } from '../theme/themeContext';
import type { ThemeContextValue } from '../theme/themeContext';

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
