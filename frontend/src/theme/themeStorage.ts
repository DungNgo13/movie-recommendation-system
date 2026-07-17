/**
 * Theme storage utilities.
 *
 * Provides typed helpers for persisting and resolving the user's
 * theme preference.  All localStorage access is wrapped in try/catch
 * so the app remains functional when storage is unavailable.
 */

// ── Types ──────────────────────────────────────────────────────────────

/** The user-selected mode stored in localStorage. */
export type ThemeMode = 'light' | 'dark' | 'system';

/** The actual visual theme applied to the document. */
export type ResolvedTheme = 'light' | 'dark';

// ── Constants ──────────────────────────────────────────────────────────

export const THEME_STORAGE_KEY = 'movie-app-theme';

const VALID_MODES: readonly ThemeMode[] = ['light', 'dark', 'system'] as const;

// ── Storage helpers ────────────────────────────────────────────────────

/**
 * Read the persisted theme mode from localStorage.
 * Returns `'system'` when the stored value is missing or invalid.
 */
export function loadThemeMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw && (VALID_MODES as readonly string[]).includes(raw)) {
      return raw as ThemeMode;
    }
  } catch {
    // localStorage may be unavailable (private browsing, SSR, etc.)
  }
  return 'system';
}

/**
 * Persist the selected theme mode to localStorage.
 * Fails silently when storage is unavailable.
 */
export function saveThemeMode(mode: ThemeMode): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // Fail silently — the user just won't get persistence.
  }
}

// ── Resolution ─────────────────────────────────────────────────────────

/**
 * Query the operating system / browser color-scheme preference.
 * Falls back to `'light'` when `matchMedia` is unavailable.
 */
export function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'light';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

/**
 * Resolve a `ThemeMode` to the concrete `ResolvedTheme` that should
 * be applied to the UI.
 */
export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === 'light' || mode === 'dark') return mode;
  return getSystemTheme();
}

// ── DOM application ────────────────────────────────────────────────────

/**
 * Apply the resolved theme to `<html>` so that CSS `:root[data-theme]`
 * selectors take effect globally.
 */
export function applyThemeToDOM(theme: ResolvedTheme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}
