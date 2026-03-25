import { describe, it, expect } from 'vitest';
import {
  filterBySearch,
  filterByYear,
  sortMovies,
  getUniqueYears,
  applyFilters,
} from './movieFilters';
import type { MovieListItem } from '../models';

const movies: MovieListItem[] = [
  { id: '1', title: 'The Dark Knight', poster_url: null, release_year: 2008 },
  { id: '2', title: 'Inception', poster_url: null, release_year: 2010 },
  { id: '3', title: 'Interstellar', poster_url: null, release_year: 2014 },
  { id: '4', title: 'The Dark Knight Rises', poster_url: null, release_year: 2012 },
  { id: '5', title: 'Avatar', poster_url: null, release_year: 2009 },
  { id: '6', title: 'Avengers', poster_url: null, release_year: 2012 },
];

describe('movieFilters', () => {
  describe('filterBySearch', () => {
    it('returns all movies for empty query', () => {
      expect(filterBySearch(movies, '')).toEqual(movies);
    });

    it('returns all movies for whitespace-only query', () => {
      expect(filterBySearch(movies, '   ')).toEqual(movies);
    });

    it('filters by title case-insensitively', () => {
      const result = filterBySearch(movies, 'dark');
      expect(result).toHaveLength(2);
      expect(result.map((m) => m.id)).toEqual(['1', '4']);
    });

    it('matches partial title', () => {
      const result = filterBySearch(movies, 'inter');
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe('3');
    });

    it('returns empty for no match', () => {
      expect(filterBySearch(movies, 'zzzzz')).toEqual([]);
    });
  });

  describe('filterByYear', () => {
    it('returns all movies when year is null', () => {
      expect(filterByYear(movies, null)).toEqual(movies);
    });

    it('filters movies by exact year', () => {
      const result = filterByYear(movies, 2012);
      expect(result).toHaveLength(2);
      expect(result.map((m) => m.id)).toEqual(['4', '6']);
    });

    it('returns empty when no movie matches year', () => {
      expect(filterByYear(movies, 1999)).toEqual([]);
    });
  });

  describe('sortMovies', () => {
    it('sorts by title ascending', () => {
      const result = sortMovies(movies, 'title-asc');
      expect(result[0].title).toBe('Avatar');
      expect(result[result.length - 1].title).toBe('The Dark Knight Rises');
    });

    it('sorts by title descending', () => {
      const result = sortMovies(movies, 'title-desc');
      expect(result[0].title).toBe('The Dark Knight Rises');
      expect(result[result.length - 1].title).toBe('Avatar');
    });

    it('sorts by year descending (newest first)', () => {
      const result = sortMovies(movies, 'year-desc');
      expect(result[0].release_year).toBe(2014);
    });

    it('sorts by year ascending (oldest first)', () => {
      const result = sortMovies(movies, 'year-asc');
      expect(result[0].release_year).toBe(2008);
    });

    it('does not mutate the original array', () => {
      const copy = [...movies];
      sortMovies(movies, 'title-asc');
      expect(movies).toEqual(copy);
    });
  });

  describe('getUniqueYears', () => {
    it('returns unique years sorted descending', () => {
      const years = getUniqueYears(movies);
      expect(years).toEqual([2014, 2012, 2010, 2009, 2008]);
    });

    it('returns empty for empty list', () => {
      expect(getUniqueYears([])).toEqual([]);
    });

    it('excludes null release years', () => {
      const withNull: MovieListItem[] = [
        ...movies,
        { id: '7', title: 'Unknown', poster_url: null, release_year: null },
      ];
      const years = getUniqueYears(withNull);
      expect(years).not.toContain(null);
    });
  });

  describe('applyFilters', () => {
    it('applies search + filter + sort together', () => {
      const result = applyFilters(movies, 'av', 2012, 'title-asc');
      // search "av" → Avengers (2012); filter year 2012 → Avengers
      expect(result).toHaveLength(1);
      expect(result[0].title).toBe('Avengers');
    });

    it('returns empty when combined filters match nothing', () => {
      const result = applyFilters(movies, 'dark', 2014, 'title-asc');
      expect(result).toEqual([]);
    });

    it('works with no filters (empty search, null year)', () => {
      const result = applyFilters(movies, '', null, 'title-asc');
      expect(result).toHaveLength(movies.length);
      expect(result[0].title).toBe('Avatar');
    });
  });
});
