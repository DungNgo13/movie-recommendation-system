import { getToken } from './authService';
import type { MovieListItem } from '../models';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface HistoryItem extends MovieListItem {
  watched_at: string;
  playback_position_seconds?: number;
  progress_percent?: number;
  is_completed?: boolean;
}

export interface WatchProgress {
  movie_id: string;
  current_time_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  is_completed: boolean;
  watched_at?: string;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Save watch progress with full timing data.
 * Used during playback for real resume support.
 */
export const saveWatchProgress = async (
  movieId: string,
  currentTimeSeconds: number,
  durationSeconds: number,
): Promise<void> => {
  const token = getToken();
  if (!token) return;

  const progressPercent =
    durationSeconds > 0
      ? Math.min((currentTimeSeconds / durationSeconds) * 100, 100)
      : 0;

  await fetch(`${API_BASE_URL}/watch-progress`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      movie_id: movieId,
      current_time_seconds: Math.floor(currentTimeSeconds),
      duration_seconds: Math.floor(durationSeconds),
      progress_percent: parseFloat(progressPercent.toFixed(2)),
    }),
  });
};

/**
 * Fetch resume position for a movie.
 * Returns current_time_seconds = 0 if no record or movie is completed.
 */
export const getWatchProgress = async (movieId: string): Promise<WatchProgress> => {
  const token = getToken();
  const empty: WatchProgress = {
    movie_id: movieId,
    current_time_seconds: 0,
    duration_seconds: 0,
    progress_percent: 0,
    is_completed: false,
  };
  if (!token) return empty;

  try {
    const res = await fetch(`${API_BASE_URL}/watch-progress/${movieId}`, {
      headers: authHeaders(),
    });
    if (!res.ok) return empty;
    return res.json();
  } catch {
    return empty;
  }
};

/**
 * Backward-compatible: record a watch event with only position.
 * Used for the initial page-open record and legacy call sites.
 */
export const recordWatch = async (movieId: string, playbackSeconds: number = 0): Promise<void> => {
  const token = getToken();
  if (!token) return;

  await fetch(`${API_BASE_URL}/history/${movieId}`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ playback_position_seconds: Math.floor(playbackSeconds) }),
  });
};

/**
 * Backward-compatible: get raw playback position from old history endpoint.
 */
export const getWatchStatus = async (movieId: string): Promise<{ playback_position_seconds: number }> => {
  const token = getToken();
  if (!token) return { playback_position_seconds: 0 };

  try {
    const res = await fetch(`${API_BASE_URL}/history/${movieId}`, {
      headers: authHeaders(),
    });
    if (!res.ok) return { playback_position_seconds: 0 };
    return res.json();
  } catch {
    return { playback_position_seconds: 0 };
  }
};

/**
 * Gets the current user's watch history list.
 */
export const getWatchHistory = async (limit = 10): Promise<HistoryItem[]> => {
  const token = getToken();
  if (!token) return [];

  const res = await fetch(`${API_BASE_URL}/history/me?limit=${limit}`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  return res.json();
};
