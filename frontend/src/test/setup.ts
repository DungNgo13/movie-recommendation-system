import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

type TranslationOptions = Record<string, unknown>;

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, arg2?: string | TranslationOptions, arg3?: TranslationOptions) => {
      let options: TranslationOptions | undefined;
      let defaultValue: string | undefined;

      if (typeof arg2 === 'string') {
        defaultValue = arg2;
        options = arg3;
      } else if (typeof arg2 === 'object') {
        options = arg2;
      }

      let str = defaultValue || key;
      if (options) {
        for (const k in options) {
          str = str.replace(`{{${k}}}`, String(options[k]));
        }
      }
      return str;
    },
    i18n: {
      changeLanguage: () => new Promise(() => {}),
      language: 'en',
    },
  }),
}));

afterEach(() => {
  cleanup();
});
