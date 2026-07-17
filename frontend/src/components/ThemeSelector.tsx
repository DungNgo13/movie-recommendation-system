import React from 'react';
import { useTheme } from '../hooks/useTheme';
import type { ThemeMode } from '../theme/themeStorage';
import { useTranslation } from 'react-i18next';

// ── Inline SVG icons (no external dependency) ──────────────────────────

const SunIcon: React.FC = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="5" />
    <line x1="12" y1="1" x2="12" y2="3" />
    <line x1="12" y1="21" x2="12" y2="23" />
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
    <line x1="1" y1="12" x2="3" y2="12" />
    <line x1="21" y1="12" x2="23" y2="12" />
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
  </svg>
);

const MoonIcon: React.FC = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

const MonitorIcon: React.FC = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
    <line x1="8" y1="21" x2="16" y2="21" />
    <line x1="12" y1="17" x2="12" y2="21" />
  </svg>
);

// ── Component ──────────────────────────────────────────────────────────

interface ThemeOption {
  mode: ThemeMode;
  labelKey: string;
  defaultLabel: string;
  Icon: React.FC;
}

const OPTIONS: ThemeOption[] = [
  { mode: 'light',  labelKey: 'common:theme.light',  defaultLabel: 'Light',  Icon: SunIcon },
  { mode: 'dark',   labelKey: 'common:theme.dark',   defaultLabel: 'Dark',   Icon: MoonIcon },
  { mode: 'system', labelKey: 'common:theme.system', defaultLabel: 'System', Icon: MonitorIcon },
];

const ThemeSelector: React.FC = () => {
  const { mode, setMode } = useTheme();
  const { t } = useTranslation();

  return (
    <div className="theme-selector" role="group" aria-label={t('common:theme.title', 'Theme settings')}>
      {OPTIONS.map(({ mode: optionMode, labelKey, defaultLabel, Icon }) => (
        <button
          key={optionMode}
          type="button"
          className={`theme-btn ${mode === optionMode ? 'active' : ''}`}
          onClick={() => setMode(optionMode)}
          aria-pressed={mode === optionMode}
          title={t(labelKey, defaultLabel)}
        >
          <Icon />
          <span className="theme-selector__label">{t(labelKey, defaultLabel)}</span>
        </button>
      ))}
    </div>
  );
};

export default ThemeSelector;
