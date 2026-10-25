/**
 * State machine for the direct-to-R2 source-video upload.
 *
 *   idle ─start─▶ requesting_url ─▶ uploading ─▶ verifying ─▶ completed
 *                       │               │            │
 *                       ▼               ▼            ▼
 *                     failed       failed/cancelled  failed ─retryCompletion─▶ verifying
 *
 * A failed completion keeps the session ID so the admin can retry ONLY the
 * verification step (the backend completion endpoint is idempotent). The file
 * is never re-uploaded automatically.
 *
 * HLS encoding is intentionally NOT triggered here: the FFmpeg pipeline cannot
 * read R2 sources yet.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Movie } from '../models';
import { getMovieById } from '../services/movieService';
import {
  R2UploadError,
  completeR2UploadSession,
  createR2UploadSession,
  putFileToR2,
  validateR2VideoFile,
} from '../services/r2UploadService';
import type {
  R2UploadErrorKind,
  R2UploadStage,
  UploadSessionCreateResponse,
} from '../services/r2UploadService';

export type R2UploadPhase =
  | 'idle'
  | 'requesting_url'
  | 'uploading'
  | 'verifying'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface R2UploadFailure {
  stage: R2UploadStage | 'validation';
  kind: R2UploadErrorKind | 'invalid_type' | 'empty' | 'too_large';
  status: number | null;
  message: string;
}

export interface R2UploadState {
  phase: R2UploadPhase;
  fileName: string | null;
  loaded: number;
  total: number;
  error: R2UploadFailure | null;
  /** True when the PUT succeeded but verification failed in a retryable way. */
  canRetryCompletion: boolean;
}

export const INITIAL_R2_UPLOAD_STATE: R2UploadState = {
  phase: 'idle',
  fileName: null,
  loaded: 0,
  total: 0,
  error: null,
  canRetryCompletion: false,
};

/**
 * Percentage to display. Reflects real transferred bytes but is capped at 99
 * until the backend has confirmed the object — 100% means "verified".
 */
export function displayPercent(state: Pick<R2UploadState, 'phase' | 'loaded' | 'total'>): number {
  if (state.phase === 'completed') return 100;
  if (state.total <= 0) return 0;
  return Math.min(99, Math.floor((state.loaded / state.total) * 100));
}

export interface UseR2DirectUploadOptions {
  movieId: string;
  /** Called after verified completion with the refreshed movie (null if refresh failed). */
  onCompleted?: (movie: Movie | null) => void;
  /** Called on HTTP 401 from our API (e.g. to redirect to /login). */
  onUnauthorized?: () => void;
  maxBytes?: number;
}

export interface UseR2DirectUpload {
  state: R2UploadState;
  start: (file: File) => Promise<void>;
  cancel: () => void;
  retryCompletion: () => Promise<void>;
  reset: () => void;
}

function toFailure(err: unknown, fallbackStage: R2UploadStage): R2UploadFailure {
  if (err instanceof R2UploadError) {
    return { stage: err.stage, kind: err.kind, status: err.status, message: err.message };
  }
  return {
    stage: fallbackStage,
    kind: 'unknown',
    status: null,
    message: err instanceof Error ? err.message : 'Unexpected error',
  };
}

export function useR2DirectUpload(options: UseR2DirectUploadOptions): UseR2DirectUpload {
  const { movieId, maxBytes } = options;
  const [state, setState] = useState<R2UploadState>(INITIAL_R2_UPLOAD_STATE);

  const callbacksRef = useRef({ onCompleted: options.onCompleted, onUnauthorized: options.onUnauthorized });
  useEffect(() => {
    callbacksRef.current = { onCompleted: options.onCompleted, onUnauthorized: options.onUnauthorized };
  }, [options.onCompleted, options.onUnauthorized]);

  const mountedRef = useRef(true);
  const busyRef = useRef(false);
  const abortRef = useRef<(() => void) | null>(null);
  const cancelRequestedRef = useRef(false);
  /** Session awaiting (re)verification; never contains the presigned URL. */
  const pendingSessionRef = useRef<{ movieId: string; sessionId: string } | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.(); // don't leave a transfer running after unmount
    };
  }, []);

  const update = useCallback((patch: Partial<R2UploadState>) => {
    if (mountedRef.current) setState((prev) => ({ ...prev, ...patch }));
  }, []);

  const fail = useCallback((failure: R2UploadFailure, canRetryCompletion = false) => {
    busyRef.current = false;
    if (failure.kind === 'unauthorized') callbacksRef.current.onUnauthorized?.();
    update({ phase: 'failed', error: failure, canRetryCompletion });
  }, [update]);

  const runCompletion = useCallback(async () => {
    const pending = pendingSessionRef.current;
    if (!pending) return;
    busyRef.current = true;
    update({ phase: 'verifying', error: null, canRetryCompletion: false });
    try {
      await completeR2UploadSession(pending.movieId, pending.sessionId);
    } catch (err) {
      const retryable = err instanceof R2UploadError && err.retryable;
      if (!retryable) pendingSessionRef.current = null;
      fail(toFailure(err, 'complete'), retryable);
      return;
    }
    pendingSessionRef.current = null;
    busyRef.current = false;

    let refreshed: Movie | null = null;
    try {
      refreshed = await getMovieById(pending.movieId);
    } catch {
      refreshed = null; // completion is already durable; a stale view is acceptable
    }
    update({ phase: 'completed', error: null, canRetryCompletion: false });
    callbacksRef.current.onCompleted?.(refreshed);
  }, [fail, update]);

  const start = useCallback(async (file: File) => {
    if (busyRef.current) return;

    const validation = validateR2VideoFile(file, maxBytes);
    if (!validation.ok) {
      setState({
        ...INITIAL_R2_UPLOAD_STATE,
        phase: 'failed',
        fileName: file.name,
        error: { stage: 'validation', kind: validation.reason, status: null, message: validation.reason },
      });
      return;
    }

    busyRef.current = true;
    cancelRequestedRef.current = false;
    pendingSessionRef.current = null;
    setState({ ...INITIAL_R2_UPLOAD_STATE, phase: 'requesting_url', fileName: file.name, total: file.size });

    let created: UploadSessionCreateResponse;
    try {
      created = await createR2UploadSession(movieId, {
        filename: file.name,
        content_type: validation.contentType,
        size: file.size,
      });
    } catch (err) {
      fail(toFailure(err, 'presign'));
      return;
    }

    if (cancelRequestedRef.current) {
      // Session stays pending server-side and expires; the cleanup job reaps it.
      busyRef.current = false;
      update({ phase: 'cancelled' });
      return;
    }
    if (created.upload_method.toUpperCase() !== 'PUT') {
      fail({ stage: 'presign', kind: 'unknown', status: null, message: 'Unsupported upload method' });
      return;
    }

    update({ phase: 'uploading', loaded: 0, total: file.size });
    const handle = putFileToR2(created.upload_url, file, created.upload_headers, ({ loaded, total }) => {
      update({ loaded, total });
    });
    abortRef.current = handle.abort;

    try {
      await handle.promise;
    } catch (err) {
      abortRef.current = null;
      if (err instanceof R2UploadError && err.kind === 'aborted') {
        busyRef.current = false;
        update({ phase: 'cancelled' });
        return;
      }
      fail(toFailure(err, 'put'));
      return;
    }
    abortRef.current = null;

    // The bytes are in R2 now; from here on only verification may be retried.
    pendingSessionRef.current = { movieId, sessionId: created.session.id };
    update({ loaded: file.size, total: file.size });
    await runCompletion();
  }, [fail, maxBytes, movieId, runCompletion, update]);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current();
    } else if (busyRef.current) {
      cancelRequestedRef.current = true; // takes effect once the URL request returns
    }
  }, []);

  const retryCompletion = useCallback(async () => {
    if (busyRef.current || !pendingSessionRef.current) return;
    await runCompletion();
  }, [runCompletion]);

  const reset = useCallback(() => {
    if (busyRef.current) return;
    pendingSessionRef.current = null;
    setState(INITIAL_R2_UPLOAD_STATE);
  }, []);

  return { state, start, cancel, retryCompletion, reset };
}
