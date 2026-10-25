/**
 * Loads and tracks the admin-only source-storage state of a movie so the form
 * knows — even after a page refresh — whether the active source is local or R2.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { MovieSourceStatusError, getMovieSourceStatus } from '../services/movieSourceService';
import type { MovieSourceStatus, SourceStorage } from '../services/movieSourceService';

export interface UseMovieSourceStatus {
  status: MovieSourceStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** Optimistically reflect a just-finished upload, then re-sync from the server. */
  markActive: (storage: SourceStorage) => void;
}

export function useMovieSourceStatus(
  movieId: string | null,
  onUnauthorized?: () => void,
): UseMovieSourceStatus {
  const [status, setStatus] = useState<MovieSourceStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const unauthorizedRef = useRef(onUnauthorized);
  useEffect(() => { unauthorizedRef.current = onUnauthorized; }, [onUnauthorized]);

  const load = useCallback(async (id: string) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    try {
      const next = await getMovieSourceStatus(id);
      if (requestId !== requestIdRef.current) return; // a newer request superseded this one
      setStatus(next);
      setError(null);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      if (err instanceof MovieSourceStatusError && err.status === 401) {
        unauthorizedRef.current?.();
      }
      setError(err instanceof Error ? err.message : 'Failed to load source status');
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!movieId) return;
    void load(movieId);
    return () => { requestIdRef.current += 1; }; // ignore late responses after unmount/change
  }, [movieId, load]);

  const refresh = useCallback(async () => {
    if (movieId) await load(movieId);
  }, [movieId, load]);

  const markActive = useCallback((storage: SourceStorage) => {
    if (!movieId) return;
    setStatus((prev) => ({
      movie_id: movieId,
      processing_status: prev?.processing_status ?? null,
      hls_ready: prev?.hls_ready ?? false,
      source_storage: storage,
      source_available: true,
      hls_processing_supported: storage === 'local',
    }));
    void load(movieId);
  }, [movieId, load]);

  return { status, loading, error, refresh, markActive };
}
