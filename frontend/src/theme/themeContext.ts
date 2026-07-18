import { createContext } from 'react';
import type { ThemeMode, ResolvedTheme } from './themeStorage';

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
