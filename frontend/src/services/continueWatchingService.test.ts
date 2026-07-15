import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Tests for continueWatchingService — verifies the real HTTP method,
 * URL, payload shape, error handling, and guest localStorage logic.
 *
 * These tests do NOT mock the service itself; they mock `fetch` and
 * `localStorage` to observe what the service actually sends.
 */

// Mock authService so we can control token availability
vi.mock('./authService', () => ({
  getToken: vi.fn(),
}));

// Mock config to use a predictable base URL
vi.mock('../config', () => ({
  API_BASE_URL: 'https://api.test.example/api/v1',
}));

import { getToken } from './authService';
import {
  saveWatchProgress,
  getWatchProgress,
  saveGuestWatchProgress,
  getGuestWatchHistory,
  getGuestWatchProgressForMovie,
  clearGuestWatchHistory,
  getWatchHistory,
} from './continueWatchingService';

const mockGetToken = getToken as ReturnType<typeof vi.fn>;

// ── Helpers ──────────────────────────────────────────────────────────────────

let fetchCalls: { url: string; init: RequestInit }[] = [];

function mockFetchOk(responseBody: unknown = {}) {
  fetchCalls = [];
  globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    fetchCalls.push({ url: String(url), init: init || {} });
    return {
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => responseBody,
    } as Response;
  });
}

function mockFetchFail(status: number) {
  fetchCalls = [];
  globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    fetchCalls.push({ url: String(url), init: init || {} });
    return {
      ok: false,
      status,
      statusText: 'Error',
      json: async () => ({}),
    } as Response;
  });
}

// ── Save watch progress ──────────────────────────────────────────────────────

describe('saveWatchProgress', () => {
  beforeEach(() => {
    mockGetToken.mockReturnValue('test-jwt-token');
    mockFetchOk();
  });

  it('sends POST to /watch-progress with correct payload', async () => {
    await saveWatchProgress('movie-abc', 120, 1800);

    expect(fetchCalls).toHaveLength(1);
    const { url, init } = fetchCalls[0];
    expect(url).toBe('https://api.test.example/api/v1/watch-progress');
    expect(init.method).toBe('POST');

    const body = JSON.parse(init.body as string);
    expect(body.movie_id).toBe('movie-abc');
    expect(body.current_time_seconds).toBe(120);
    expect(body.duration_seconds).toBe(1800);
    expect(body.progress_percent).toBeCloseTo(6.67, 1);
  });

  it('sends Authorization header with Bearer token', async () => {
    await saveWatchProgress('movie-abc', 60, 600);

    const headers = fetchCalls[0].init.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('skips save when no token is available', async () => {
    mockGetToken.mockReturnValue(null);
    await saveWatchProgress('movie-abc', 60, 600);

    expect(fetchCalls).toHaveLength(0);
  });

  it('floors currentTime and duration to integers', async () => {
    await saveWatchProgress('movie-abc', 120.7, 1800.3);

    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.current_time_seconds).toBe(120);
    expect(body.duration_seconds).toBe(1800);
  });

  it('clamps progress_percent to 100 max', async () => {
    await saveWatchProgress('movie-abc', 2000, 1800);

    const body = JSON.parse(fetchCalls[0].init.body as string);
    expect(body.progress_percent).toBeLessThanOrEqual(100);
  });

  it('does not throw when fetch returns non-ok status', async () => {
    mockFetchFail(422);
    // Should not throw
    await expect(saveWatchProgress('movie-abc', 60, 600)).resolves.toBeUndefined();
  });

  it('does not throw when fetch rejects (network error)', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('Network error')));
    await expect(saveWatchProgress('movie-abc', 60, 600)).resolves.toBeUndefined();
  });

  it('uses keepalive when specified', async () => {
    await saveWatchProgress('movie-abc', 120, 1800, true);

    expect(fetchCalls[0].init.keepalive).toBe(true);
  });
});

// ── Get watch progress ───────────────────────────────────────────────────────

describe('getWatchProgress', () => {
  beforeEach(() => {
    mockGetToken.mockReturnValue('test-jwt-token');
  });

  it('sends GET to /watch-progress/{movieId}', async () => {
    const mockData = {
      movie_id: 'movie-abc',
      current_time_seconds: 300,
      duration_seconds: 1800,
      progress_percent: 16.7,
      is_completed: false,
    };
    mockFetchOk(mockData);

    const result = await getWatchProgress('movie-abc');

    expect(fetchCalls).toHaveLength(1);
    expect(fetchCalls[0].url).toBe('https://api.test.example/api/v1/watch-progress/movie-abc');
    expect(result.current_time_seconds).toBe(300);
    expect(result.is_completed).toBe(false);
  });

  it('returns empty progress when no token', async () => {
    mockGetToken.mockReturnValue(null);
    const result = await getWatchProgress('movie-abc');

    expect(result.current_time_seconds).toBe(0);
    expect(result.is_completed).toBe(false);
  });

  it('returns empty progress on non-ok response', async () => {
    mockFetchFail(404);
    const result = await getWatchProgress('movie-abc');

    expect(result.current_time_seconds).toBe(0);
  });
});

// ── Get watch history (Continue Watching list) ───────────────────────────────

describe('getWatchHistory', () => {
  beforeEach(() => {
    mockGetToken.mockReturnValue('test-jwt-token');
    fetchCalls = [];
  });

  it('sends GET to /history/me with limit', async () => {
    mockFetchOk([]);
    await getWatchHistory(5);

    expect(fetchCalls[0].url).toBe('https://api.test.example/api/v1/history/me?limit=5');
  });

  it('returns empty array when no token', async () => {
    mockGetToken.mockReturnValue(null);
    const result = await getWatchHistory();

    expect(result).toEqual([]);
    expect(fetchCalls).toHaveLength(0);
  });
});

// ── Guest localStorage ───────────────────────────────────────────────────────

describe('guest watch progress (localStorage)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('saves and reads guest progress', () => {
    saveGuestWatchProgress('movie-1', 120, 1800);

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].movie_id).toBe('movie-1');
    expect(history[0].current_time_seconds).toBe(120);
    expect(history[0].duration_seconds).toBe(1800);
    expect(history[0].progress_percent).toBeCloseTo(6.67, 1);
  });

  it('upserts by movie_id — does not create duplicates', () => {
    saveGuestWatchProgress('movie-1', 60, 1800);
    saveGuestWatchProgress('movie-1', 300, 1800);

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].current_time_seconds).toBe(300);
  });

  it('tracks multiple movies independently', () => {
    saveGuestWatchProgress('movie-1', 60, 1800);
    saveGuestWatchProgress('movie-2', 120, 3600);

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(2);
  });

  it('getGuestWatchProgressForMovie returns correct entry', () => {
    saveGuestWatchProgress('movie-1', 120, 1800);
    saveGuestWatchProgress('movie-2', 300, 3600);

    const progress = getGuestWatchProgressForMovie('movie-1');
    expect(progress).not.toBeNull();
    expect(progress!.current_time_seconds).toBe(120);
  });

  it('getGuestWatchProgressForMovie returns null for unknown movie', () => {
    const progress = getGuestWatchProgressForMovie('movie-999');
    expect(progress).toBeNull();
  });

  it('clearGuestWatchHistory removes all data', () => {
    saveGuestWatchProgress('movie-1', 60, 1800);
    clearGuestWatchHistory();

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(0);
  });

  it('handles corrupt localStorage gracefully', () => {
    localStorage.setItem('guest_watch_history', 'not-json');
    const history = getGuestWatchHistory();
    expect(history).toEqual([]);
  });
});
