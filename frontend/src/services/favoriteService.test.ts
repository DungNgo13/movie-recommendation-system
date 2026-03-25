import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getFavoriteMovieIds,
  isFavoriteMovie,
  toggleFavoriteMovie,
} from './favoriteService';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((_index: number) => null),
  };
})();

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });

describe('favoriteService', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('getFavoriteMovieIds', () => {
    it('returns empty array when localStorage is empty', () => {
      expect(getFavoriteMovieIds()).toEqual([]);
    });

    it('returns stored IDs', () => {
      localStorageMock.setItem('favoriteMovieIds', JSON.stringify(['1', '2']));
      expect(getFavoriteMovieIds()).toEqual(['1', '2']);
    });

    it('returns empty array for corrupted JSON', () => {
      localStorageMock.setItem('favoriteMovieIds', 'not-json');
      expect(getFavoriteMovieIds()).toEqual([]);
    });

    it('returns empty array if stored value is not an array', () => {
      localStorageMock.setItem('favoriteMovieIds', JSON.stringify({ a: 1 }));
      expect(getFavoriteMovieIds()).toEqual([]);
    });

    it('filters out non-string values from array', () => {
      localStorageMock.setItem(
        'favoriteMovieIds',
        JSON.stringify(['1', 2, null, '3']),
      );
      expect(getFavoriteMovieIds()).toEqual(['1', '3']);
    });
  });

  describe('isFavoriteMovie', () => {
    it('returns true for a favorited movie', () => {
      localStorageMock.setItem('favoriteMovieIds', JSON.stringify(['42']));
      expect(isFavoriteMovie('42')).toBe(true);
    });

    it('returns false for a non-favorited movie', () => {
      localStorageMock.setItem('favoriteMovieIds', JSON.stringify(['42']));
      expect(isFavoriteMovie('99')).toBe(false);
    });

    it('returns false for empty string ID', () => {
      expect(isFavoriteMovie('')).toBe(false);
    });
  });

  describe('toggleFavoriteMovie', () => {
    it('adds a movie ID when not present', () => {
      const result = toggleFavoriteMovie('42');
      expect(result).toEqual(['42']);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'favoriteMovieIds',
        JSON.stringify(['42']),
      );
    });

    it('removes a movie ID when already present', () => {
      localStorageMock.setItem('favoriteMovieIds', JSON.stringify(['42', '99']));
      const result = toggleFavoriteMovie('42');
      expect(result).toEqual(['99']);
    });

    it('does nothing for empty string ID', () => {
      localStorageMock.setItem('favoriteMovieIds', JSON.stringify(['42']));
      const result = toggleFavoriteMovie('');
      expect(result).toEqual(['42']);
    });

    it('can toggle multiple times correctly', () => {
      toggleFavoriteMovie('1');
      toggleFavoriteMovie('2');
      expect(getFavoriteMovieIds()).toEqual(['1', '2']);

      toggleFavoriteMovie('1');
      expect(getFavoriteMovieIds()).toEqual(['2']);

      toggleFavoriteMovie('1');
      expect(getFavoriteMovieIds()).toEqual(['2', '1']);
    });
  });
});
