/**
 * useAutoRefreshSession — Sliding Session Hook
 *
 * Monitors user activity (mouse, keyboard, scroll, video play) and silently
 * refreshes the JWT when:
 *   1. The user is active, AND
 *   2. The current token has lived past 50% of its lifetime (4h of 8h).
 *
 * DESIGN DECISIONS (thesis-defensible):
 *
 *   Throttling: Activity events fire at high frequency (mousemove, scroll).
 *   We record the timestamp of the last activity but only evaluate a refresh
 *   on a 60-second interval timer — this prevents spamming the /auth/refresh
 *   endpoint while still keeping the check responsive.
 *
 *   Non-disruptive: The refresh call is a background fetch. It does NOT
 *   trigger a React state update, page reload, or re-render of the HLS
 *   player. Only localStorage is touched (atomic setItem).
 *
 *   Graceful failure: If the refresh fails (network error, token already
 *   expired), the hook silently stops. The user's current session continues
 *   until the original token naturally expires, at which point the normal
 *   401 → redirect-to-login flow takes over.
 */

import { useEffect, useRef } from 'react';
import { getToken, refreshToken } from '../services/authService';

// ─── JWT helpers (decode without verification — safe for client-side age check) ─

/** Decode the payload of a JWT without verifying the signature. */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

/** Return how many seconds ago the token was issued (based on `iat` claim). */
function tokenAgeSeconds(token: string): number {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.iat !== 'number') return 0;
  return Math.floor(Date.now() / 1000) - (payload.iat as number);
}

/** Return the token's total lifetime in seconds (exp - iat). */
function tokenLifetimeSeconds(token: string): number {
  const payload = decodeJwtPayload(token);
  if (
    !payload ||
    typeof payload.iat !== 'number' ||
    typeof payload.exp !== 'number'
  )
    return 0;
  return (payload.exp as number) - (payload.iat as number);
}

// ─── Hook ────────────────────────────────────────────────────────────────────

/** How often (ms) we check whether a refresh is needed. */
const CHECK_INTERVAL_MS = 60_000; // 1 minute

/** Minimum seconds of inactivity before we stop refreshing. */
const ACTIVITY_WINDOW_MS = 5 * 60_000; // 5 minutes

/**
 * Fraction of token lifetime that must elapse before a refresh is attempted.
 * 0.5 = 50 % → for an 8-hour token, refresh after 4 hours of active use.
 */
const REFRESH_THRESHOLD = 0.5;

export function useAutoRefreshSession(): void {
  // Tracks the timestamp of the most recent user activity.
  // Using a ref (not state) so updates never trigger re-renders.
  const lastActivityRef = useRef<number>(Date.now());

  // Guard against overlapping refresh calls.
  const refreshingRef = useRef(false);

  // ── Register activity listeners ──────────────────────────────────────────
  useEffect(() => {
    const markActive = () => {
      lastActivityRef.current = Date.now();
    };

    // Standard DOM events that prove the user is present.
    const events: (keyof WindowEventMap)[] = [
      'mousedown',
      'keydown',
      'scroll',
      'touchstart',
    ];
    events.forEach((evt) => window.addEventListener(evt, markActive, { passive: true }));

    // Custom event emitted by the HLS player during playback — counts as
    // activity even if the user hasn't touched the mouse or keyboard.
    window.addEventListener('video-play-activity' as keyof WindowEventMap, markActive);

    return () => {
      events.forEach((evt) => window.removeEventListener(evt, markActive));
      window.removeEventListener('video-play-activity' as keyof WindowEventMap, markActive);
    };
  }, []);

  // ── Periodic refresh check ───────────────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(async () => {
      // 1. Is there a token at all?
      const token = getToken();
      if (!token) return;

      // 2. Was the user active recently?
      const idleMs = Date.now() - lastActivityRef.current;
      if (idleMs > ACTIVITY_WINDOW_MS) return;

      // 3. Is the token old enough to warrant a refresh?
      const age = tokenAgeSeconds(token);
      const lifetime = tokenLifetimeSeconds(token);
      if (lifetime <= 0) return; // malformed token
      if (age / lifetime < REFRESH_THRESHOLD) return; // still fresh

      // 4. Avoid concurrent refresh calls.
      if (refreshingRef.current) return;
      refreshingRef.current = true;

      try {
        await refreshToken(); // updates localStorage atomically
      } finally {
        refreshingRef.current = false;
      }
    }, CHECK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);
}
