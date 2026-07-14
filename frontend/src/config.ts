/**
 * Centralized API configuration.
 *
 * Reads the backend URL from Vite's environment variable system.
 * In development, VITE_API_BASE_URL defaults to http://localhost:8000/api/v1.
 * In production, set VITE_API_BASE_URL in .env.production to the real backend URL.
 *
 * Usage:  import { API_BASE_URL } from '../config';
 *
 * Every service file imports from here — no hardcoded URLs anywhere else.
 */
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL: string =

  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/**
 * Resolve a media URL to a safe, same-origin path.
 *
 * - Returns `null` for missing values.
 * - Preserves valid external HTTPS URLs.
 * - Strips stale internal `http://` domains (e.g. old IP addresses)
 *   and extracts the `/media/…` path portion.
 * - Ensures relative paths have a leading `/`.
 * - Prevents Mixed Content errors on HTTPS deployments.
 *
 * Use this for poster, backdrop, video, and HLS playlist URLs.
 */
export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;

  // External HTTPS URL — pass through.
  if (path.startsWith('https://')) return path;

  // Stale internal HTTP URL (e.g. http://172.35.53.158/media/...).
  // Extract the /media/… portion and discard the scheme + host.
  if (path.startsWith('http://')) {
    const idx = path.indexOf('/media/');
    if (idx >= 0) return path.slice(idx);
    return null; // non-media HTTP URL — reject
  }

  // Ensure leading slash for relative paths.
  if (!path.startsWith('/')) return `/${path}`;

  return path;
}

  configuredApiBaseUrl?.replace(/\/+$/, '') || '/api/v1';

