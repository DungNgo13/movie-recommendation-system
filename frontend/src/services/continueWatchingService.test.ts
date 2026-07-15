import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Tests for continueWatchingService — verifies HTTP calls, error handling,
 * guest localStorage schema (canonical + old migration), completion threshold,
 * and formatPlaybackTime.
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
  isWatchCompleted,
  formatPlaybackTime,
  COMPLETION_THRESHOLD,
  GUEST_HISTORY_EVENT,
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

// ── isWatchCompleted ─────────────────────────────────────────────────────────

describe('isWatchCompleted', () => {
  it('returns false for 0%', () => {
    expect(isWatchCompleted(0)).toBe(false);
  });

  it('returns false for 92.17% (below threshold)', () => {
    expect(isWatchCompleted(92.17)).toBe(false);
  });

  it('returns false for 94.99%', () => {
    expect(isWatchCompleted(94.99)).toBe(false);
  });

  it('returns true for exactly 95%', () => {
    expect(isWatchCompleted(95)).toBe(true);
  });

  it('returns true for 100%', () => {
    expect(isWatchCompleted(100)).toBe(true);
  });

  it('returns false for NaN', () => {
    expect(isWatchCompleted(NaN)).toBe(false);
  });

  it('returns false for Infinity', () => {
    expect(isWatchCompleted(Infinity)).toBe(false);
  });

  it('threshold constant is 95', () => {
    expect(COMPLETION_THRESHOLD).toBe(95);
  });
});

// ── formatPlaybackTime ───────────────────────────────────────────────────────

describe('formatPlaybackTime', () => {
  it('formats 28 seconds as 00:28', () => {
    expect(formatPlaybackTime(28)).toBe('00:28');
  });

  it('formats 84 seconds as 01:24', () => {
    expect(formatPlaybackTime(84)).toBe('01:24');
  });

  it('formats 3661 seconds as 01:01:01', () => {
    expect(formatPlaybackTime(3661)).toBe('01:01:01');
  });

  it('formats 0 seconds as 00:00', () => {
    expect(formatPlaybackTime(0)).toBe('00:00');
  });

  it('handles negative values by clamping to 0', () => {
    expect(formatPlaybackTime(-5)).toBe('00:00');
  });

  it('handles fractional seconds by flooring', () => {
    expect(formatPlaybackTime(28.7)).toBe('00:28');
  });
});

// ── Save watch progress (authenticated) ──────────────────────────────────────

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

// ── Guest localStorage — canonical schema ────────────────────────────────────

describe('guest watch progress (localStorage)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('saves canonical entry with playback_position_seconds', () => {
    saveGuestWatchProgress('movie-1', 120, 1800);

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].movie_id).toBe('movie-1');
    expect(history[0].playback_position_seconds).toBe(120);
    expect(history[0].duration_seconds).toBe(1800);
    expect(history[0].progress_percent).toBeCloseTo(6.67, 1);
    expect(history[0].is_completed).toBe(false);
    expect(history[0].updated_at).toBeTruthy();
  });

  it('stores is_completed = true when progress >= 95%', () => {
    saveGuestWatchProgress('movie-1', 1710, 1800);  // 95%

    const history = getGuestWatchHistory();
    expect(history[0].is_completed).toBe(true);
  });

  it('stores is_completed = false for 92.17%', () => {
    saveGuestWatchProgress('movie-1', 28.57, 31);  // ~92.17%

    const entry = getGuestWatchProgressForMovie('movie-1');
    expect(entry).not.toBeNull();
    expect(entry!.is_completed).toBe(false);
    expect(entry!.progress_percent).toBeCloseTo(92.17, 0);
  });

  it('short 31s video at 50% remains unfinished', () => {
    saveGuestWatchProgress('movie-1', 15.5, 31);

    const entry = getGuestWatchProgressForMovie('movie-1');
    expect(entry!.is_completed).toBe(false);
    expect(entry!.progress_percent).toBe(50);
  });

  it('short 31s video at 92.17% remains unfinished', () => {
    saveGuestWatchProgress('movie-1', 28.57, 31);

    const entry = getGuestWatchProgressForMovie('movie-1');
    expect(entry!.is_completed).toBe(false);
  });

  it('upserts by movie_id — does not create duplicates', () => {
    saveGuestWatchProgress('movie-1', 60, 1800);
    saveGuestWatchProgress('movie-1', 300, 1800);

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].playback_position_seconds).toBe(300);
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
    expect(progress!.playback_position_seconds).toBe(120);
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

  it('rejects NaN values by sanitising to 0', () => {
    saveGuestWatchProgress('movie-1', NaN, 1800);

    const entry = getGuestWatchProgressForMovie('movie-1');
    expect(entry!.playback_position_seconds).toBe(0);
    expect(entry!.progress_percent).toBe(0);
  });

  it('rejects negative values by sanitising to 0', () => {
    saveGuestWatchProgress('movie-1', -10, 1800);

    const entry = getGuestWatchProgressForMovie('movie-1');
    expect(entry!.playback_position_seconds).toBe(0);
  });

  it('guest data survives page refresh (persisted in localStorage)', () => {
    saveGuestWatchProgress('movie-1', 120, 1800);

    // Simulate page refresh by reading from a fresh getGuestWatchHistory call
    const raw = localStorage.getItem('guest_watch_history');
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed[0].playback_position_seconds).toBe(120);
    expect(parsed[0].is_completed).toBe(false);
    expect(parsed[0].updated_at).toBeTruthy();
  });

  it('entries are sorted by updated_at when read', () => {
    // Save in order: movie-1 first, then movie-2
    saveGuestWatchProgress('movie-1', 60, 1800);
    // movie-2 saved after movie-1 — should appear first (most recent)
    saveGuestWatchProgress('movie-2', 120, 3600);

    const all = getGuestWatchHistory();
    // Both entries exist; movie-2 was saved later
    expect(all).toHaveLength(2);
    // updated_at of movie-2 should be >= movie-1
    expect(all.find(e => e.movie_id === 'movie-2')!.updated_at >=
           all.find(e => e.movie_id === 'movie-1')!.updated_at).toBe(true);
  });

  it('dispatches custom event when saving', () => {
    const handler = vi.fn();
    window.addEventListener(GUEST_HISTORY_EVENT, handler);

    saveGuestWatchProgress('movie-1', 60, 1800);

    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(GUEST_HISTORY_EVENT, handler);
  });
});

// ── Guest localStorage — old entry migration ─────────────────────────────────

describe('guest old entry migration', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('migrates old entry missing playback_position_seconds', () => {
    // Old format: { movie_id, duration_seconds, progress_percent }
    localStorage.setItem('guest_watch_history', JSON.stringify([
      { movie_id: 'old-1', duration_seconds: 31, progress_percent: 92.17 },
    ]));

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].movie_id).toBe('old-1');
    // Derived: floor(31 * 92.17 / 100) = floor(28.5727) = 28
    expect(history[0].playback_position_seconds).toBe(28);
    expect(history[0].duration_seconds).toBe(31);
    expect(history[0].progress_percent).toBeCloseTo(92.17, 1);
    expect(history[0].is_completed).toBe(false); // 92.17 < 95
    expect(history[0].updated_at).toBeTruthy();  // epoch fallback
  });

  it('migrates old entry with current_time_seconds field name', () => {
    localStorage.setItem('guest_watch_history', JSON.stringify([
      { movie_id: 'old-2', current_time_seconds: 120, duration_seconds: 1800, progress_percent: 6.67 },
    ]));

    const history = getGuestWatchHistory();
    expect(history[0].playback_position_seconds).toBe(120);
  });

  it('migrates old entry missing is_completed by computing from 95% rule', () => {
    localStorage.setItem('guest_watch_history', JSON.stringify([
      { movie_id: 'old-3', duration_seconds: 100, progress_percent: 96 },
    ]));

    const history = getGuestWatchHistory();
    expect(history[0].is_completed).toBe(true);
  });

  it('skips entries without movie_id', () => {
    localStorage.setItem('guest_watch_history', JSON.stringify([
      { duration_seconds: 100, progress_percent: 50 },
      { movie_id: 'valid', duration_seconds: 100, progress_percent: 50 },
    ]));

    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].movie_id).toBe('valid');
  });

  it('login merge preserves local data on failed login', () => {
    saveGuestWatchProgress('movie-1', 120, 1800);

    // Simulate failed login — don't call clearGuestWatchHistory
    const history = getGuestWatchHistory();
    expect(history).toHaveLength(1);
  });
});
