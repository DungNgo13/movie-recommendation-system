import { getToken } from './authService';

import { API_BASE_URL } from '../config';

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

/**
 * Get the current user's rating for a specific movie.
 * Returns null if not rated or not logged in.
 */
export const getMyRating = async (movieId: string): Promise<number | null> => {
  const token = getToken();
  if (!token) return null;

  const response = await fetch(`${API_BASE_URL}/ratings/${movieId}/me`, {
    headers: authHeaders(),
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data.rating ?? null;
};

/**
 * Rate a movie (create or update). Rating must be 1-5.
 */
export const rateMovie = async (movieId: string, rating: number): Promise<void> => {
  const token = getToken();
  if (!token) return;

  const response = await fetch(`${API_BASE_URL}/ratings`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ movie_id: movieId, rating }),
  });
  if (!response.ok) {
    throw new Error('Failed to rate movie');
  }
};
