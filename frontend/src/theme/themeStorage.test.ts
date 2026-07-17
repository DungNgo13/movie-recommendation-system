import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  loadThemeMode,
  saveThemeMode,
  resolveTheme,
  getSystemTheme,
  applyThemeToDOM,
  THEME_STORAGE_KEY,
} from './themeStorage';

// ── Helper: mock matchMedia ───────────────────────────────────────────

function mockMatchMedia(prefersDark: boolean) {
  const listeners: Array<(e: MediaQueryListEvent) => void> = [];
  const mql: MediaQueryList = {
    matches: prefersDark,
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_event: string, cb: (e: MediaQueryListEvent) => void) => {
      listeners.push(cb);
    }) as MediaQueryList['addEventListener'],
    removeEventListener: vi.fn((_event: string, cb: (e: MediaQueryListEvent) => void) => {
      const idx = listeners.indexOf(cb);
      if (idx >= 0) listeners.splice(idx, 1);
    }) as MediaQueryList['removeEventListener'],
    dispatchEvent: vi.fn(),
  };
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(mql));
  return { mql, listeners };
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('themeStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── loadThemeMode ──

  it('returns "system" when localStorage is empty', () => {
    expect(loadThemeMode()).toBe('system');
  });

  it('returns "system" for invalid stored value "black"', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'black');
    expect(loadThemeMode()).toBe('system');
  });

  it('returns "system" for invalid stored value "undefined"', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'undefined');
    expect(loadThemeMode()).toBe('system');
  });

  it('returns "system" for invalid stored value "null"', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'null');
    expect(loadThemeMode()).toBe('system');
  });

  it('returns "system" for invalid stored JSON object', () => {
    localStorage.setItem(THEME_STORAGE_KEY, '{"theme":"dark"}');
    expect(loadThemeMode()).toBe('system');
  });

  it('returns "light" when stored value is "light"', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    expect(loadThemeMode()).toBe('light');
  });

  it('returns "dark" when stored value is "dark"', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    expect(loadThemeMode()).toBe('dark');
  });

  it('returns "system" when stored value is "system"', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'system');
    expect(loadThemeMode()).toBe('system');
  });

  it('returns "system" when localStorage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage disabled');
    });
    expect(loadThemeMode()).toBe('system');
  });

  // ── saveThemeMode ──

  it('persists mode to localStorage', () => {
    saveThemeMode('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('does not crash when localStorage throws on write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage full');
    });
    expect(() => saveThemeMode('light')).not.toThrow();
  });

  // ── resolveTheme ──

  it('"light" resolves to "light" regardless of system preference', () => {
    mockMatchMedia(true); // system is dark
    expect(resolveTheme('light')).toBe('light');
  });

  it('"dark" resolves to "dark" regardless of system preference', () => {
    mockMatchMedia(false); // system is light
    expect(resolveTheme('dark')).toBe('dark');
  });

  it('"system" resolves to "dark" when prefers-color-scheme: dark', () => {
    mockMatchMedia(true);
    expect(resolveTheme('system')).toBe('dark');
  });

  it('"system" resolves to "light" when prefers-color-scheme: light', () => {
    mockMatchMedia(false);
    expect(resolveTheme('system')).toBe('light');
  });

  // ── getSystemTheme ──

  it('returns "light" when matchMedia is unavailable', () => {
    vi.stubGlobal('matchMedia', undefined);
    expect(getSystemTheme()).toBe('light');
  });

  // ── applyThemeToDOM ──

  it('sets data-theme and color-scheme on <html>', () => {
    applyThemeToDOM('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('can switch theme from dark to light', () => {
    applyThemeToDOM('dark');
    applyThemeToDOM('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });
});
