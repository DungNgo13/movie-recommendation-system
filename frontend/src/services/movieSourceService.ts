/**
 * Admin-only source-video storage state
 * (GET {API}/admin/movies/{movieId}/source).
 *
 * The response never contains object keys, bucket names, paths or URLs.
 */
import { API_BASE_URL } from '../config';
import { getToken } from './authService';

export type SourceStorage = 'local' | 'r2';

export interface MovieSourceStatus {
  movie_id: string;
  source_storage: SourceStorage;
  source_available: boolean;
  processing_status: string | null;
  hls_ready: boolean;
  hls_processing_supported: boolean;
}

export class MovieSourceStatusError extends Error {
  readonly status: number | null;
  readonly code: string | null;

  constructor(message: string, status: number | null, code: string | null = null) {
    super(message);
    this.name = 'MovieSourceStatusError';
    this.status = status;
    this.code = code;
  }
}

export async function getMovieSourceStatus(
  movieId: string,
  signal?: AbortSignal,
): Promise<MovieSourceStatus> {
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/admin/movies/${encodeURIComponent(movieId)}/source`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new MovieSourceStatusError('Network error while loading source status', null);
  }

  if (response.ok) return response.json() as Promise<MovieSourceStatus>;

  const body: { detail?: unknown; code?: unknown } | null = await response.json().catch(() => null);
  const detail = typeof body?.detail === 'string' ? body.detail : `Failed to load source status (HTTP ${response.status})`;
  const code = typeof body?.code === 'string' ? body.code : null;
  throw new MovieSourceStatusError(detail, response.status, code);
}
