import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadLanguage, saveLanguage, isAppLanguage, LANGUAGE_STORAGE_KEY } from './languageStorage';

describe('languageStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('isAppLanguage', () => {
    it('returns true for valid languages', () => {
      expect(isAppLanguage('en')).toBe(true);
      expect(isAppLanguage('vi')).toBe(true);
    });

    it('returns false for invalid languages', () => {
      expect(isAppLanguage('fr')).toBe(false);
      expect(isAppLanguage(null)).toBe(false);
      expect(isAppLanguage(undefined)).toBe(false);
      expect(isAppLanguage(123)).toBe(false);
      expect(isAppLanguage({})).toBe(false);
    });
  });

  describe('saveLanguage', () => {
    it('saves the language to localStorage', () => {
      saveLanguage('en');
      expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');

      saveLanguage('vi');
      expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('vi');
    });

    it('handles localStorage exceptions gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.spyOn(Storage.prototype, 'setItem').mockImplementationOnce(() => {
        throw new Error('Quota exceeded');
      });

      expect(() => saveLanguage('en')).not.toThrow();
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('loadLanguage', () => {
    it('loads the language from localStorage if valid', () => {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, 'en');
      expect(loadLanguage()).toBe('en');
    });

    it('returns default (vi) if no language is stored', () => {
      expect(loadLanguage()).toBe('vi');
    });

    it('returns default (vi) if stored language is invalid', () => {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, 'invalid');
      expect(loadLanguage()).toBe('vi');
    });

    it('handles localStorage exceptions gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.spyOn(Storage.prototype, 'getItem').mockImplementationOnce(() => {
        throw new Error('Access denied');
      });

      expect(loadLanguage()).toBe('vi');
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });
});
