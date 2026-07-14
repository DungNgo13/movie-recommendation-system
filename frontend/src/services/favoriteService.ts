import { getToken } from './authService';

import { API_BASE_URL } from '../config';

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Fetches the list of favorite movie IDs for the current user.
 */
export const getFavoriteMovieIds = async (): Promise<string[]> => {
  const token = getToken();
  if (!token) return [];

  const response = await fetch(`${API_BASE_URL}/favorites/me/ids`, {
    headers: authHeaders(),
  });
  if (!response.ok) return [];
  return response.json();
};

/**
 * Adds a movie to favorites.
 */
export const addFavoriteMovie = async (movieId: string): Promise<void> => {
  await fetch(`${API_BASE_URL}/favorites/${movieId}`, {
    method: 'POST',
    headers: authHeaders(),
  });
};

/**
 * Removes a movie from favorites.
 */
export const removeFavoriteMovie = async (movieId: string): Promise<void> => {
  await fetch(`${API_BASE_URL}/favorites/${movieId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
};

// ─────────────────────────────────────────────────────────────────────────────
// Guest (unauthenticated) localStorage favorites
// ─────────────────────────────────────────────────────────────────────────────

const GUEST_FAVORITES_KEY = 'guest_favorite_ids';

/**
 * Read guest favorite movie IDs from localStorage.
 */
export const getGuestFavoriteIds = (): string[] => {
  try {
    const raw = localStorage.getItem(GUEST_FAVORITES_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
};

/**
 * Add a movie ID to guest favorites (localStorage). Deduplicates.
 */
export const addGuestFavorite = (movieId: string): void => {
  const ids = getGuestFavoriteIds();
  if (!ids.includes(movieId)) {
    ids.push(movieId);
    localStorage.setItem(GUEST_FAVORITES_KEY, JSON.stringify(ids));
  }
};

/**
 * Remove a movie ID from guest favorites (localStorage).
 */
export const removeGuestFavorite = (movieId: string): void => {
  const ids = getGuestFavoriteIds().filter((id) => id !== movieId);
  localStorage.setItem(GUEST_FAVORITES_KEY, JSON.stringify(ids));
};

/**
 * Remove all guest favorite data from localStorage.
 * Called after a successful merge into the authenticated user's account.
 */
export const clearGuestFavorites = (): void => {
  localStorage.removeItem(GUEST_FAVORITES_KEY);
};

/**
 * POST guest favorite IDs to the backend merge endpoint.
 * Returns the number of newly merged favorites.
 */
export const mergeGuestFavorites = async (movieIds: string[]): Promise<number> => {
  const token = getToken();
  if (!token || movieIds.length === 0) return 0;

  const response = await fetch(`${API_BASE_URL}/favorites/me/merge`, {
    method: 'POST',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ movie_ids: movieIds }),
  });

  if (!response.ok) return 0;
  const data = await response.json();
  return data.merged ?? 0;
};
