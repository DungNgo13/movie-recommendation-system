import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getContinueWatchingMovie,
  setContinueWatchingMovie,
  clearContinueWatchingMovie,
} from './continueWatchingService';

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

describe('continueWatchingService', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('getContinueWatchingMovie', () => {
    it('returns null when localStorage is empty', () => {
      expect(getContinueWatchingMovie()).toBeNull();
    });

    it('returns stored movie', () => {
      const movie = { id: '1', title: 'Inception', poster_url: '/img.jpg', release_year: 2010 };
      localStorageMock.setItem('continueWatchingMovie', JSON.stringify(movie));
      expect(getContinueWatchingMovie()).toEqual(movie);
    });

    it('returns null for corrupted JSON', () => {
      localStorageMock.setItem('continueWatchingMovie', 'not-json');
      expect(getContinueWatchingMovie()).toBeNull();
    });

    it('returns null if stored value has no id', () => {
      localStorageMock.setItem('continueWatchingMovie', JSON.stringify({ title: 'Test' }));
      expect(getContinueWatchingMovie()).toBeNull();
    });

    it('returns null if id is empty string', () => {
      localStorageMock.setItem(
        'continueWatchingMovie',
        JSON.stringify({ id: '', title: 'Test', poster_url: null, release_year: null }),
      );
      expect(getContinueWatchingMovie()).toBeNull();
    });

    it('handles missing optional fields gracefully', () => {
      localStorageMock.setItem(
        'continueWatchingMovie',
        JSON.stringify({ id: '1', title: 'Test' }),
      );
      expect(getContinueWatchingMovie()).toEqual({
        id: '1',
        title: 'Test',
        poster_url: null,
        release_year: null,
      });
    });
  });

  describe('setContinueWatchingMovie', () => {
    it('saves a movie to localStorage', () => {
      const movie = { id: '1', title: 'Inception', poster_url: '/img.jpg', release_year: 2010 };
      setContinueWatchingMovie(movie);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'continueWatchingMovie',
        JSON.stringify(movie),
      );
    });

    it('does nothing for movie with empty id', () => {
      setContinueWatchingMovie({ id: '', title: 'Test', poster_url: null, release_year: null });
      expect(localStorageMock.setItem).not.toHaveBeenCalled();
    });

    it('overwrites previous movie', () => {
      setContinueWatchingMovie({ id: '1', title: 'A', poster_url: null, release_year: null });
      setContinueWatchingMovie({ id: '2', title: 'B', poster_url: null, release_year: 2020 });
      expect(getContinueWatchingMovie()?.id).toBe('2');
      expect(getContinueWatchingMovie()?.title).toBe('B');
    });
  });

  describe('clearContinueWatchingMovie', () => {
    it('removes the movie from localStorage', () => {
      setContinueWatchingMovie({ id: '1', title: 'Test', poster_url: null, release_year: null });
      clearContinueWatchingMovie();
      expect(getContinueWatchingMovie()).toBeNull();
    });
  });
});
