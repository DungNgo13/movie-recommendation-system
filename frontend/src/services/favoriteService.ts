import { getToken } from './authService';

const API_BASE_URL = 'http://localhost:8000/api/v1';

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
