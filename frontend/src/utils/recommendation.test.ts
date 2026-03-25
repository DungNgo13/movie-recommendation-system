import { describe, it, expect } from 'vitest';
import { extractKeywords, calculateScore, getRecommendations } from './recommendation';
import type { MovieListItem } from '../models';

describe('recommendation', () => {
  describe('extractKeywords', () => {
    it('returns empty array for empty string', () => {
      expect(extractKeywords('')).toEqual([]);
    });

    it('extracts meaningful words from title', () => {
      expect(extractKeywords('The Dark Knight')).toEqual(['dark', 'knight']);
    });

    it('filters out stop words and short tokens', () => {
      expect(extractKeywords('A Star Is Born')).toEqual(['star', 'born']);
    });

    it('handles special characters', () => {
      expect(extractKeywords("Spider-Man: No Way Home")).toEqual(['spiderman', 'way', 'home']);
    });

    it('lowercases all keywords', () => {
      expect(extractKeywords('INCEPTION')).toEqual(['inception']);
    });
  });

  describe('calculateScore', () => {
    const makeMovie = (overrides: Partial<MovieListItem> = {}): MovieListItem => ({
      id: '1',
      title: 'Test Movie',
      poster_url: null,
      release_year: 2020,
      ...overrides,
    });

    it('scores +3 per matching keyword', () => {
      const context = { titleKeywords: ['dark', 'knight'], releaseYear: null };
      const candidate = makeMovie({ title: 'The Dark Knight Rises' });
      // 'dark' matches (+3), 'knight' matches (+3) = 6
      expect(calculateScore(candidate, context)).toBe(6);
    });

    it('scores +2 for same release year', () => {
      const context = { titleKeywords: [], releaseYear: 2020 };
      const candidate = makeMovie({ release_year: 2020 });
      expect(calculateScore(candidate, context)).toBe(2);
    });

    it('scores +1 for release year within 1-2 years', () => {
      const context = { titleKeywords: [], releaseYear: 2020 };
      const candidate1 = makeMovie({ release_year: 2021 });
      const candidate2 = makeMovie({ release_year: 2018 });
      expect(calculateScore(candidate1, context)).toBe(1);
      expect(calculateScore(candidate2, context)).toBe(1);
    });

    it('scores 0 for release year >2 years apart', () => {
      const context = { titleKeywords: [], releaseYear: 2020 };
      const candidate = makeMovie({ release_year: 2010 });
      expect(calculateScore(candidate, context)).toBe(0);
    });

    it('handles null release years gracefully', () => {
      const context = { titleKeywords: [], releaseYear: null };
      const candidate = makeMovie({ release_year: null });
      expect(calculateScore(candidate, context)).toBe(0);
    });

    it('combines keyword + year scores', () => {
      const context = { titleKeywords: ['dark', 'knight'], releaseYear: 2008 };
      const candidate = makeMovie({ title: 'The Dark Knight Rises', release_year: 2008 });
      // keywords: 6 + year: 2 = 8
      expect(calculateScore(candidate, context)).toBe(8);
    });
  });

  describe('getRecommendations', () => {
    const movies: MovieListItem[] = [
      { id: '1', title: 'The Dark Knight', poster_url: null, release_year: 2008 },
      { id: '2', title: 'The Dark Knight Rises', poster_url: null, release_year: 2012 },
      { id: '3', title: 'Batman Begins', poster_url: null, release_year: 2005 },
      { id: '4', title: 'Inception', poster_url: null, release_year: 2010 },
      { id: '5', title: 'Interstellar', poster_url: null, release_year: 2014 },
      { id: '6', title: 'The Prestige', poster_url: null, release_year: 2006 },
    ];

    it('excludes the current movie', () => {
      const results = getRecommendations('1', 'The Dark Knight', 2008, movies);
      expect(results.every((m) => m.id !== '1')).toBe(true);
    });

    it('returns at most limit results', () => {
      const results = getRecommendations('1', 'The Dark Knight', 2008, movies, 3);
      expect(results.length).toBeLessThanOrEqual(3);
    });

    it('ranks movies with matching keywords higher', () => {
      const results = getRecommendations('1', 'The Dark Knight', 2008, movies);
      // 'The Dark Knight Rises' should be first (matches dark + knight)
      expect(results[0].id).toBe('2');
    });

    it('returns empty array for empty movie list', () => {
      expect(getRecommendations('1', 'Test', 2020, [])).toEqual([]);
    });

    it('returns empty array for empty movieId', () => {
      expect(getRecommendations('', 'Test', 2020, movies)).toEqual([]);
    });

    it('returns other movies as fallback when no keyword matches', () => {
      const results = getRecommendations('4', 'Inception', 2010, movies);
      expect(results.length).toBeGreaterThan(0);
      expect(results.every((m) => m.id !== '4')).toBe(true);
    });

    it('defaults to limit of 4', () => {
      const results = getRecommendations('1', 'The Dark Knight', 2008, movies);
      expect(results.length).toBeLessThanOrEqual(4);
    });
  });
});
