import React, { createContext, useState, useEffect, useCallback, useMemo } from 'react';
import type { ThemeMode, ResolvedTheme } from './themeStorage';
import {
  loadThemeMode,
  saveThemeMode,
  resolveTheme,
  applyThemeToDOM,
} from './themeStorage';

// ── Context value ──────────────────────────────────────────────────────

export interface ThemeContextValue {
  /** The user-selected mode (light | dark | system). */
  mode: ThemeMode;
  /** The concrete theme currently applied to the UI. */
  resolvedTheme: ResolvedTheme;
  /** Update the theme mode — persists to localStorage. */
  setMode: (mode: ThemeMode) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

// ── Provider ───────────────────────────────────────────────────────────

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setModeState] = useState<ThemeMode>(() => loadThemeMode());
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    resolveTheme(loadThemeMode()),
  );

  // Public setter — persists + resolves + applies.
  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    saveThemeMode(newMode);
    const resolved = resolveTheme(newMode);
    setResolvedTheme(resolved);
    applyThemeToDOM(resolved);
  }, []);

  // Apply on mount (in case the inline script in index.html missed it).
  useEffect(() => {
    applyThemeToDOM(resolvedTheme);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Listen for OS theme changes only when mode === 'system'.
  useEffect(() => {
    if (mode !== 'system') return;

    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (event: MediaQueryListEvent) => {
      const newResolved: ResolvedTheme = event.matches ? 'dark' : 'light';
      setResolvedTheme(newResolved);
      applyThemeToDOM(newResolved);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, [mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, resolvedTheme, setMode }),
    [mode, resolvedTheme, setMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
