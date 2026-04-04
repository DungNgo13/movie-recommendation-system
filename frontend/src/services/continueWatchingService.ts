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
export const recordWatch = async (movieId: string, playbackSeconds: number = 0): Promise<void> => {
  const token = getToken();
  if (!token) return;

  await fetch(`${API_BASE_URL}/history/${movieId}`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ playback_position_seconds: Math.floor(playbackSeconds) })
  });
};

/**
 * Gets specific view metrics for tracking.
 */
export const getWatchStatus = async (movieId: string): Promise<{ playback_position_seconds: number }> => {
  const token = getToken();
  if (!token) return { playback_position_seconds: 0 };

  try {
    const response = await fetch(`${API_BASE_URL}/history/${movieId}`, {
      headers: authHeaders(),
    });
    if (!response.ok) return { playback_position_seconds: 0 };
    return response.json();
  } catch {
    return { playback_position_seconds: 0 };
  }
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
