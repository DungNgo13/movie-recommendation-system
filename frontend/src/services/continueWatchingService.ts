import type { MovieListItem } from '../models';

const STORAGE_KEY = 'continueWatchingMovie';

/**
 * Retrieves the continue-watching movie from localStorage.
 * Returns null if not set or data is corrupted.
 */
export const getContinueWatchingMovie = (): MovieListItem | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      !('id' in parsed) ||
      !('title' in parsed)
    ) {
      return null;
    }
    const obj = parsed as Record<string, unknown>;
    if (typeof obj.id !== 'string' || !obj.id) return null;
    if (typeof obj.title !== 'string') return null;

    return {
      id: obj.id,
      title: obj.title,
      poster_url: typeof obj.poster_url === 'string' ? obj.poster_url : null,
      release_year: typeof obj.release_year === 'number' ? obj.release_year : null,
    };
  } catch {
    return null;
  }
};

/**
 * Saves a movie as the continue-watching movie.
 * Does nothing if movie is null or has no valid id.
 */
export const setContinueWatchingMovie = (movie: MovieListItem): void => {
  if (!movie || !movie.id) return;

  const data: MovieListItem = {
    id: movie.id,
    title: movie.title,
    poster_url: movie.poster_url,
    release_year: movie.release_year,
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
};

/**
 * Clears the continue-watching movie from localStorage.
 */
export const clearContinueWatchingMovie = (): void => {
  localStorage.removeItem(STORAGE_KEY);
};
