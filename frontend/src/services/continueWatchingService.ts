import { getToken } from './authService';
import type { MovieListItem } from '../models';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface HistoryItem extends MovieListItem {
  watched_at: string;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Records that the current user watched a movie.
 */
export const recordWatch = async (movieId: string): Promise<void> => {
  const token = getToken();
  if (!token) return;

  await fetch(`${API_BASE_URL}/history/${movieId}`, {
    method: 'POST',
    headers: authHeaders(),
  });
};

/**
 * Gets the current user's watch history.
 */
export const getWatchHistory = async (limit = 10): Promise<HistoryItem[]> => {
  const token = getToken();
  if (!token) return [];

  const response = await fetch(`${API_BASE_URL}/history/me?limit=${limit}`, {
    headers: authHeaders(),
  });
  if (!response.ok) return [];
  return response.json();
};
