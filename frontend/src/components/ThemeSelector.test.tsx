import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '../theme/ThemeContext';
import ThemeSelector from './ThemeSelector';
import { THEME_STORAGE_KEY } from '../theme/themeStorage';

// ── matchMedia mock ────────────────────────────────────────────────────

function setupMatchMedia(dark = false) {
  const mql: MediaQueryList = {
    matches: dark,
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(mql));
}

function renderSelector() {
  return render(
    <ThemeProvider>
      <ThemeSelector />
    </ThemeProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────

describe('ThemeSelector', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.style.removeProperty('color-scheme');
    setupMatchMedia(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Rendering ──

  it('renders the theme control group', () => {
    renderSelector();
    const group = screen.getByRole('group', { name: /theme settings/i });
    expect(group).toBeTruthy();
  });

  it('renders Light, Dark, and System buttons', () => {
    renderSelector();
    expect(screen.getByRole('button', { name: /light/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /dark/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /system/i })).toBeTruthy();
  });

  // ── Active state ──

  it('marks System as active by default', () => {
    renderSelector();
    const systemBtn = screen.getByRole('button', { name: /system/i });
    expect(systemBtn.getAttribute('aria-pressed')).toBe('true');
  });

  it('marks Light as active when selected', async () => {
    renderSelector();
    const lightBtn = screen.getByRole('button', { name: /light/i });
    await userEvent.click(lightBtn);
    expect(lightBtn.getAttribute('aria-pressed')).toBe('true');

    const darkBtn = screen.getByRole('button', { name: /dark/i });
    expect(darkBtn.getAttribute('aria-pressed')).toBe('false');
  });

  it('marks Dark as active when selected', async () => {
    renderSelector();
    const darkBtn = screen.getByRole('button', { name: /dark/i });
    await userEvent.click(darkBtn);
    expect(darkBtn.getAttribute('aria-pressed')).toBe('true');
  });

  // ── Theme application ──

  it('clicking Dark sets data-theme="dark"', async () => {
    renderSelector();
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('clicking Light sets data-theme="light"', async () => {
    renderSelector();
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  // ── Persistence ──

  it('saves selection to localStorage', async () => {
    renderSelector();
    await userEvent.click(screen.getByRole('button', { name: /dark/i }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  // ── Keyboard ──

  it('buttons are keyboard accessible with Tab and Enter', async () => {
    renderSelector();
    const user = userEvent.setup();

    // Tab to Light button
    await user.tab();
    const lightBtn = screen.getByRole('button', { name: /light/i });
    expect(document.activeElement).toBe(lightBtn);

    // Press Enter to activate
    await user.keyboard('{Enter}');
    expect(lightBtn.getAttribute('aria-pressed')).toBe('true');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  // ── All buttons have type="button" ──

  it('all buttons have type="button"', () => {
    renderSelector();
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn.getAttribute('type')).toBe('button');
    });
  });

  // ── Loaded preference ──

  it('loads stored "dark" on mount', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    renderSelector();
    const darkBtn = screen.getByRole('button', { name: /dark/i });
    expect(darkBtn.getAttribute('aria-pressed')).toBe('true');
  });

  // ── Shared segmented-control classes ──

  it('theme options use shared segmented-control classes', () => {
    const { container } = renderSelector();
    const wrapper = container.querySelector('.segmented-control');
    expect(wrapper).toBeTruthy();

    const options = container.querySelectorAll('.segmented-control__option');
    expect(options.length).toBe(3);
  });

  it('active theme option has segmented-control__option--active class', () => {
    const { container } = renderSelector();
    const activeOptions = container.querySelectorAll('.segmented-control__option--active');
    expect(activeOptions.length).toBe(1);
  });

  it('each button has an icon wrapped in segmented-control__icon', () => {
    const { container } = renderSelector();
    const icons = container.querySelectorAll('.segmented-control__icon');
    expect(icons.length).toBe(3);
    icons.forEach((icon) => {
      expect(icon.querySelector('svg')).toBeTruthy();
    });
  });

  it('each button has a label wrapped in segmented-control__label', () => {
    const { container } = renderSelector();
    const labels = container.querySelectorAll('.segmented-control__label');
    expect(labels.length).toBe(3);
  });
});
