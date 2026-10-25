/**
 * Direct-to-R2 source-video upload client.
 *
 * Backend contract (see docs/r2_direct_upload.md):
 *   1. POST {API}/admin/movies/{movieId}/uploads            → presigned PUT URL
 *   2. PUT  <upload_url> with exactly `upload_headers`      → file goes to R2
 *   3. POST {API}/admin/movies/{movieId}/uploads/{id}/complete → server HeadObject check
 *
 * Security notes:
 *   - The presigned URL is a short-lived secret capability. It is never logged,
 *     stored, or rendered; it lives only inside the XHR call below.
 *   - The PUT to R2 must NOT carry the app's Authorization header (the URL is
 *     already signed; leaking the JWT to a third-party origin is unnecessary).
 */
import { API_BASE_URL } from '../config';
import { getToken } from './authService';

// ─── Contract types (mirror backend/app/schemas/upload_session.py) ──────────

export interface UploadSession {
  id: string;
  movie_id: string;
  status: string;
  original_filename: string | null;
  content_type: string;
  expected_size: number;
  actual_size: number | null;
  error: string | null;
  created_at: string;
  expires_at: string;
  completed_at: string | null;
}

export interface UploadSessionCreateRequest {
  filename: string;
  content_type: string;
  size: number;
}

export interface UploadSessionCreateResponse {
  session: UploadSession;
  upload_url: string;
  upload_method: string;
  upload_headers: Record<string, string>;
  expires_in_seconds: number;
}

// ─── Validation ─────────────────────────────────────────────────────────────

/** Backend allow-list: content type → canonical extension. */
export const R2_ALLOWED_CONTENT_TYPES: Readonly<Record<string, string>> = {
  'video/mp4': 'mp4',
  'video/x-matroska': 'mkv',
  'video/webm': 'webm',
  'video/quicktime': 'mov',
  'video/x-msvideo': 'avi',
};

/** Browsers report some containers inconsistently (or as ""), so map by extension. */
const EXTENSION_CONTENT_TYPES: Readonly<Record<string, string>> = {
  mp4: 'video/mp4',
  m4v: 'video/mp4',
  mkv: 'video/x-matroska',
  webm: 'video/webm',
  mov: 'video/quicktime',
  avi: 'video/x-msvideo',
};

/** Common browser aliases for allowed types. */
const CONTENT_TYPE_ALIASES: Readonly<Record<string, string>> = {
  'video/avi': 'video/x-msvideo',
  'video/msvideo': 'video/x-msvideo',
  'video/x-m4v': 'video/mp4',
};

/**
 * Client-side ceiling. Mirrors the backend hard cap on R2_MAX_UPLOAD_BYTES
 * (5,000,000,000 bytes); the server may enforce a lower configured limit and
 * will answer 400, which is surfaced to the user.
 */
export const R2_CLIENT_MAX_UPLOAD_BYTES = 5_000_000_000;

export const R2_ACCEPT_ATTRIBUTE =
  'video/mp4,video/x-matroska,video/webm,video/quicktime,video/x-msvideo,.mp4,.m4v,.mkv,.webm,.mov,.avi';

/** Resolve the allowed content type for a file, or null if not allowed. */
export function resolveVideoContentType(file: Pick<File, 'name' | 'type'>): string | null {
  const reported = (file.type || '').split(';')[0].trim().toLowerCase();
  const normalized = CONTENT_TYPE_ALIASES[reported] ?? reported;
  if (normalized && normalized in R2_ALLOWED_CONTENT_TYPES) return normalized;
  // A specific but disallowed type (e.g. image/png renamed to .mp4) is rejected;
  // only an empty/generic type falls back to the extension.
  if (normalized && normalized !== 'application/octet-stream') return null;

  const dot = file.name.lastIndexOf('.');
  const ext = dot >= 0 ? file.name.slice(dot + 1).toLowerCase() : '';
  return EXTENSION_CONTENT_TYPES[ext] ?? null;
}

export type FileValidationResult =
  | { ok: true; contentType: string }
  | { ok: false; reason: 'invalid_type' | 'empty' | 'too_large' };

export function validateR2VideoFile(
  file: Pick<File, 'name' | 'type' | 'size'>,
  maxBytes: number = R2_CLIENT_MAX_UPLOAD_BYTES,
): FileValidationResult {
  const contentType = resolveVideoContentType(file);
  if (!contentType) return { ok: false, reason: 'invalid_type' };
  if (file.size <= 0) return { ok: false, reason: 'empty' };
  if (file.size > maxBytes) return { ok: false, reason: 'too_large' };
  return { ok: true, contentType };
}

// ─── Errors ─────────────────────────────────────────────────────────────────

export type R2UploadStage = 'presign' | 'put' | 'complete';

export type R2UploadErrorKind =
  | 'unauthorized'      // 401
  | 'forbidden'         // 403 from our API
  | 'not_found'         // 404 movie / session
  | 'too_large'         // 400 from initiation
  | 'validation'        // 422 on initiation (bad payload)
  | 'expired'           // presigned URL / session expired
  | 'object_missing'    // 409: object not in R2 yet (completion retryable)
  | 'conflict'          // 409: session failed/expired (new upload needed)
  | 'mismatch'          // 422 on completion: size/type mismatch
  | 'storage_error'     // 502
  | 'unavailable'       // 503
  | 'put_failed'        // R2 rejected the PUT
  | 'network'           // connection dropped / CORS blocked
  | 'aborted'           // user cancelled
  | 'unknown';

export class R2UploadError extends Error {
  readonly stage: R2UploadStage;
  readonly kind: R2UploadErrorKind;
  readonly status: number | null;
  /** True when retrying the SAME step (not re-uploading) may succeed. */
  readonly retryable: boolean;

  constructor(
    message: string,
    opts: { stage: R2UploadStage; kind: R2UploadErrorKind; status?: number | null; retryable?: boolean },
  ) {
    super(message);
    this.name = 'R2UploadError';
    this.stage = opts.stage;
    this.kind = opts.kind;
    this.status = opts.status ?? null;
    this.retryable = opts.retryable ?? false;
  }
}

/** FastAPI returns `detail` as a string or (for 422 validation) an array. */
function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === 'string') return first.msg;
    }
  }
  return fallback;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function uploadsUrl(movieId: string): string {
  return `${API_BASE_URL}/admin/movies/${encodeURIComponent(movieId)}/uploads`;
}

// ─── Step 1: initiate ───────────────────────────────────────────────────────

export async function createR2UploadSession(
  movieId: string,
  payload: UploadSessionCreateRequest,
): Promise<UploadSessionCreateResponse> {
  let response: Response;
  try {
    response = await fetch(uploadsUrl(movieId), {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });
  } catch {
    throw new R2UploadError('Network error while requesting an upload URL', {
      stage: 'presign', kind: 'network', retryable: true,
    });
  }

  if (response.ok) return response.json() as Promise<UploadSessionCreateResponse>;

  const body: unknown = await response.json().catch(() => null);
  const status = response.status;
  const message = extractDetail(body, `Could not start upload (HTTP ${status})`);
  const kind: R2UploadErrorKind =
    status === 401 ? 'unauthorized'
    : status === 403 ? 'forbidden'
    : status === 404 ? 'not_found'
    : status === 400 ? 'too_large'
    : status === 422 ? 'validation'
    : status === 502 ? 'storage_error'
    : status === 503 ? 'unavailable'
    : 'unknown';
  throw new R2UploadError(message, {
    stage: 'presign', kind, status, retryable: status === 502 || status === 503,
  });
}

// ─── Step 2: PUT to R2 ──────────────────────────────────────────────────────

export interface UploadProgress {
  loaded: number;
  total: number;
}

export interface PutHandle {
  promise: Promise<void>;
  abort: () => void;
}

/**
 * PUT the file to the presigned URL with XMLHttpRequest (fetch has no upload
 * progress). Sends exactly the signed headers returned by the backend.
 */
export function putFileToR2(
  uploadUrl: string,
  file: Blob,
  headers: Record<string, string>,
  onProgress?: (progress: UploadProgress) => void,
): PutHandle {
  const xhr = new XMLHttpRequest();

  const promise = new Promise<void>((resolve, reject) => {
    xhr.upload.addEventListener('progress', (e: ProgressEvent) => {
      if (onProgress) {
        const total = e.lengthComputable && e.total > 0 ? e.total : file.size;
        onProgress({ loaded: Math.min(e.loaded, total), total });
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
        return;
      }
      // R2 answers 403 for expired/invalid signatures. The body is S3 XML; we
      // deliberately do not surface it (it can echo request details).
      const expired = xhr.status === 403 && /expired/i.test(xhr.responseText || '');
      reject(new R2UploadError(
        expired
          ? 'The upload link expired before the transfer finished'
          : `Cloud storage rejected the upload (HTTP ${xhr.status})`,
        { stage: 'put', kind: expired ? 'expired' : 'put_failed', status: xhr.status },
      ));
    });

    xhr.addEventListener('error', () => {
      reject(new R2UploadError('Network error while uploading to cloud storage', {
        stage: 'put', kind: 'network',
      }));
    });
    xhr.addEventListener('timeout', () => {
      reject(new R2UploadError('Upload to cloud storage timed out', {
        stage: 'put', kind: 'network',
      }));
    });
    xhr.addEventListener('abort', () => {
      reject(new R2UploadError('Upload cancelled', { stage: 'put', kind: 'aborted' }));
    });

    xhr.open('PUT', uploadUrl);
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.send(file);
  });

  return { promise, abort: () => xhr.abort() };
}

// ─── Step 3: complete ───────────────────────────────────────────────────────

const OBJECT_MISSING_PREFIX = 'Uploaded object not found';

export async function completeR2UploadSession(
  movieId: string,
  sessionId: string,
): Promise<UploadSession> {
  let response: Response;
  try {
    response = await fetch(
      `${uploadsUrl(movieId)}/${encodeURIComponent(sessionId)}/complete`,
      { method: 'POST', headers: authHeaders() },
    );
  } catch {
    // Completion is idempotent server-side, so a dropped request is safe to retry.
    throw new R2UploadError('Network error while verifying the upload', {
      stage: 'complete', kind: 'network', retryable: true,
    });
  }

  if (response.ok) return response.json() as Promise<UploadSession>;

  const body: unknown = await response.json().catch(() => null);
  const status = response.status;
  const message = extractDetail(body, `Upload verification failed (HTTP ${status})`);

  let kind: R2UploadErrorKind = 'unknown';
  let retryable = false;
  switch (status) {
    case 401: kind = 'unauthorized'; break;
    case 403: kind = 'forbidden'; break;
    case 404: kind = 'not_found'; break;
    case 409:
      if (message.startsWith(OBJECT_MISSING_PREFIX)) {
        kind = 'object_missing'; retryable = true;
      } else if (/expired/i.test(message)) {
        kind = 'expired';
      } else {
        kind = 'conflict';
      }
      break;
    case 422: kind = 'mismatch'; break;
    case 502: kind = 'storage_error'; retryable = true; break;
    case 503: kind = 'unavailable'; retryable = true; break;
  }
  throw new R2UploadError(message, { stage: 'complete', kind, status, retryable });
}
