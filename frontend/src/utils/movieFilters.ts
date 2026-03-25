import type { MovieListItem } from '../models';

export type SortOption = 'title-asc' | 'title-desc' | 'year-desc' | 'year-asc';

/**
 * Filters movies by search query (case-insensitive title match).
 */
export const filterBySearch = (
  movies: MovieListItem[],
  query: string,
): MovieListItem[] => {
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return movies;
  return movies.filter((m) => m.title.toLowerCase().includes(trimmed));
};

/**
 * Filters movies by release year. Returns all if year is null.
 */
export const filterByYear = (
  movies: MovieListItem[],
  year: number | null,
): MovieListItem[] => {
  if (year === null) return movies;
  return movies.filter((m) => m.release_year === year);
};

/**
 * Sorts movies by the given sort option.
 * Returns a new sorted array (does not mutate).
 */
export const sortMovies = (
  movies: MovieListItem[],
  sort: SortOption,
): MovieListItem[] => {
  const sorted = [...movies];

  switch (sort) {
    case 'title-asc':
      sorted.sort((a, b) => a.title.localeCompare(b.title));
      break;
    case 'title-desc':
      sorted.sort((a, b) => b.title.localeCompare(a.title));
      break;
    case 'year-desc':
      sorted.sort((a, b) => (b.release_year ?? 0) - (a.release_year ?? 0));
      break;
    case 'year-asc':
      sorted.sort((a, b) => (a.release_year ?? 0) - (b.release_year ?? 0));
      break;
  }

  return sorted;
};

/**
 * Extracts unique release years from a movie list, sorted descending.
 */
export const getUniqueYears = (movies: MovieListItem[]): number[] => {
  const years = new Set<number>();
  for (const m of movies) {
    if (m.release_year !== null) {
      years.add(m.release_year);
    }
  }
  return Array.from(years).sort((a, b) => b - a);
};

/**
 * Applies search, filter, and sort in sequence.
 */
export const applyFilters = (
  movies: MovieListItem[],
  searchQuery: string,
  yearFilter: number | null,
  sort: SortOption,
): MovieListItem[] => {
  const searched = filterBySearch(movies, searchQuery);
  const filtered = filterByYear(searched, yearFilter);
  return sortMovies(filtered, sort);
};
