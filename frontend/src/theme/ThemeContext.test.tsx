import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from './ThemeContext';
import { useTheme } from '../hooks/useTheme';
import { THEME_STORAGE_KEY } from './themeStorage';

// ── matchMedia mock ────────────────────────────────────────────────────

let prefersDark = false;
let mediaListeners: Array<(e: MediaQueryListEvent) => void> = [];

function setupMatchMedia(dark: boolean) {
  prefersDark = dark;
  mediaListeners = [];
  const mql: MediaQueryList = {
    get matches() { return prefersDark; },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_: string, cb: (e: MediaQueryListEvent) => void) => {
      mediaListeners.push(cb);
    }) as MediaQueryList['addEventListener'],
    removeEventListener: vi.fn((_: string, cb: (e: MediaQueryListEvent) => void) => {
      const idx = mediaListeners.indexOf(cb);
      if (idx >= 0) mediaListeners.splice(idx, 1);
    }) as MediaQueryList['removeEventListener'],
    dispatchEvent: vi.fn(),
  };
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(mql));
  return mql;
}

function fireSystemThemeChange(dark: boolean) {
  prefersDark = dark;
  const event = { matches: dark } as MediaQueryListEvent;
  mediaListeners.forEach((cb) => cb(event));
}

// ── Test consumer component ────────────────────────────────────────────

function ThemeConsumer() {
  const { mode, resolvedTheme, setMode } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="resolved">{resolvedTheme}</span>
      <button type="button" onClick={() => setMode('light')}>Light</button>
      <button type="button" onClick={() => setMode('dark')}>Dark</button>
      <button type="button" onClick={() => setMode('system')}>System</button>
    </div>
  );
}

function renderWithTheme() {
  return render(
    <ThemeProvider>
      <ThemeConsumer />
    </ThemeProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.style.removeProperty('color-scheme');
    setupMatchMedia(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── DOM attribute application ──

  it('selecting Light sets data-theme="light"', async () => {
    renderWithTheme();
    await userEvent.click(screen.getByText('Light'));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('selecting Dark sets data-theme="dark"', async () => {
    renderWithTheme();
    await userEvent.click(screen.getByText('Dark'));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('selecting System uses current system preference (light)', async () => {
    setupMatchMedia(false);
    renderWithTheme();
    await userEvent.click(screen.getByText('System'));
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('selecting System uses current system preference (dark)', async () => {
    setupMatchMedia(true);
    renderWithTheme();
    await userEvent.click(screen.getByText('System'));
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  // ── localStorage persistence ──

  it('theme selection is saved to localStorage', async () => {
    renderWithTheme();
    await userEvent.click(screen.getByText('Dark'));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('"system" is stored as "system", not as the resolved value', async () => {
    setupMatchMedia(true);
    renderWithTheme();
    await userEvent.click(screen.getByText('System'));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('system');
  });

  // ── Stored values load correctly ──

  it('stored "light" loads correctly on mount', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    renderWithTheme();
    expect(screen.getByTestId('mode').textContent).toBe('light');
    expect(screen.getByTestId('resolved').textContent).toBe('light');
  });

  it('stored "dark" loads correctly on mount', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    renderWithTheme();
    expect(screen.getByTestId('mode').textContent).toBe('dark');
    expect(screen.getByTestId('resolved').textContent).toBe('dark');
  });

  it('stored "system" loads correctly on mount', () => {
    setupMatchMedia(true);
    localStorage.setItem(THEME_STORAGE_KEY, 'system');
    renderWithTheme();
    expect(screen.getByTestId('mode').textContent).toBe('system');
    expect(screen.getByTestId('resolved').textContent).toBe('dark');
  });

  // ── System listener ──

  it('system preference changes update the theme in System mode', async () => {
    setupMatchMedia(false);
    renderWithTheme();
    await userEvent.click(screen.getByText('System'));
    expect(screen.getByTestId('resolved').textContent).toBe('light');

    act(() => fireSystemThemeChange(true));
    expect(screen.getByTestId('resolved').textContent).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('system preference changes do NOT override manually selected Light', async () => {
    setupMatchMedia(false);
    renderWithTheme();
    await userEvent.click(screen.getByText('Light'));

    act(() => fireSystemThemeChange(true));
    expect(screen.getByTestId('resolved').textContent).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('system preference changes do NOT override manually selected Dark', async () => {
    setupMatchMedia(true);
    renderWithTheme();
    await userEvent.click(screen.getByText('Dark'));

    act(() => fireSystemThemeChange(false));
    expect(screen.getByTestId('resolved').textContent).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  // ── Listener cleanup ──

  it('media-query listeners are cleaned up when switching away from system', async () => {
    const mql = setupMatchMedia(false);
    renderWithTheme();
    await userEvent.click(screen.getByText('System'));

    const addedCount = (mql.addEventListener as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(addedCount).toBeGreaterThan(0);

    await userEvent.click(screen.getByText('Light'));

    // After switching to light, the listener should have been removed
    const removedCount = (mql.removeEventListener as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(removedCount).toBeGreaterThan(0);
  });

  // ── Invalid data safety ──

  it('invalid localStorage data does not crash rendering', () => {
    localStorage.setItem(THEME_STORAGE_KEY, '{"broken": true}');
    expect(() => renderWithTheme()).not.toThrow();
    expect(screen.getByTestId('mode').textContent).toBe('system');
  });

  it('storage failure does not crash rendering', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('disabled');
    });
    expect(() => renderWithTheme()).not.toThrow();
  });

  // ── useTheme outside provider ──

  it('useTheme throws when used outside ThemeProvider', () => {
    // Suppress React error boundary console output
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<ThemeConsumer />)).toThrow('useTheme must be used within a <ThemeProvider>');
    spy.mockRestore();
  });
});
