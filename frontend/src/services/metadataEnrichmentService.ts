import { API_BASE_URL } from '../config';
import { getToken } from './authService';

export interface FieldConflictInfo {
  status: 'missing_in_movsug' | 'identical' | 'conflict_overwrite' | 'no_proposal';
  existing_value: unknown;
  proposed_value: unknown;
  requires_explicit_overwrite: boolean;
}

export interface MetadataCandidate {
  id: string;
  job_id: string;
  movie_id: string;
  provider: string;
  provider_movie_id: string;
  source_language: string;
  title: string;
  original_title?: string | null;
  release_date?: string | null;
  release_year?: number | null;
  original_language?: string | null;
  director?: string | null;
  match_score: number;
  match_status: 'verified_id' | 'review_required' | 'ambiguous' | 'conflict' | string;
  is_verified_id_match: boolean;
  match_evidence: Record<string, unknown>;
  conflicts: string[];
  reason_for_review?: string | null;
  proposed_fields: Record<string, unknown>;
  existing_values: Record<string, unknown>;
  field_conflicts: Record<string, FieldConflictInfo>;
  review_state: string;
  retrieved_at: string;
}

export interface MetadataReviewEvent {
  id: string;
  job_id: string;
  movie_id: string;
  candidate_id?: string | null;
  reviewing_admin_email: string;
  action: string;
  review_state_before?: string | null;
  review_state_after: string;
  approved_fields?: string[] | null;
  rejected_fields?: string[] | null;
  notes?: string | null;
  created_at: string;
}

export interface MetadataFieldProvenance {
  id: string;
  movie_id: string;
  job_id: string;
  candidate_id?: string | null;
  field_name: string;
  provider: string;
  provider_movie_id: string;
  source_language: string;
  previous_value?: unknown;
  applied_value?: unknown;
  approved_by_email: string;
  retrieved_at: string;
  applied_at: string;
}

export interface MetadataEnrichmentJob {
  id: string;
  movie_id: string;
  provider: string;
  source_language: string;
  status: string;
  selected_candidate_id?: string | null;
  review_state: string;
  initiated_by_email?: string | null;
  reviewing_admin_email?: string | null;
  reviewed_at?: string | null;
  application_status: string;
  applied_at?: string | null;
  failure_reason?: string | null;
  approved_fields?: string[] | null;
  candidates_found: number;
  retry_count: number;
  http_429_count: number;
  processing_time_ms?: number | null;
  is_mocked: boolean;
  created_at: string;
  updated_at: string;
  candidates: MetadataCandidate[];
  review_events: MetadataReviewEvent[];
  provenances: MetadataFieldProvenance[];
  movie_metadata_version?: number | null;
}

export interface EnrichmentError extends Error {
  status?: number;
  code?: string;
}

/**
 * Map TMDB error codes to actionable user-facing messages.
 */
const TMDB_ERROR_MESSAGES: Record<string, string> = {
  tmdb_live_requests_disabled:
    'Live TMDB requests are disabled. An administrator must set TMDB_ENABLE_LIVE_REQUESTS=true in the backend .env and restart the server.',
  tmdb_not_configured:
    'TMDB API credentials are missing. Set TMDB_API_READ_ACCESS_TOKEN in the backend .env and restart the server.',
  tmdb_unauthorized:
    'TMDB API authentication failed (HTTP 401). Verify that the TMDB_API_READ_ACCESS_TOKEN is valid.',
  tmdb_forbidden:
    'TMDB API access forbidden (HTTP 403). The API token may lack the required permissions.',
  tmdb_rate_limited:
    'TMDB API rate limit exceeded. Please wait a moment and try again.',
  tmdb_timeout:
    'TMDB API request timed out. Check network connectivity and try again.',
  tmdb_network_error:
    "Network error connecting to TMDB. Check the server's internet connection.",
  tmdb_tls_handshake_failed:
    'TLS/SSL connection to TMDB failed. This may be caused by a firewall, proxy, or ISP restriction.',
  tmdb_circuit_open:
    'TMDB connectivity circuit breaker is open due to repeated failures. The connection will retry automatically after the server restarts.',
  tmdb_budget_exhausted:
    'TMDB request budget exhausted. No further API calls are allowed in this session.',
  tmdb_upstream_error:
    'TMDB API returned a server error. The service may be temporarily unavailable.',
  tmdb_not_found:
    'No matching movie found on TMDB for the given identifiers.',
  enrichment_duplicate_active_job:
    'An active enrichment job already exists for this movie. Approve, apply, or reject it before starting a new one.',
  enrichment_concurrent_modification:
    'The movie was modified by another user. Reload the page and try again.',
};

function authHeaders(json = true): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (json) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    let detail = fallbackMessage;
    let code: string | undefined;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') {
        detail = body.detail;
      }
      if (typeof body?.code === 'string') {
        code = body.code;
      }
    } catch {
      // ignore JSON parse failure
    }
    // Use actionable message when a known TMDB/enrichment error code is returned
    const actionableMessage = code ? TMDB_ERROR_MESSAGES[code] : undefined;
    const err = new Error(actionableMessage || detail) as EnrichmentError;
    err.status = response.status;
    err.code = code;
    throw err;
  }
  return response.json();
}

export async function startMovieEnrichment(
  movieId: string,
  options?: {
    source_language?: string;
    include_vi_localization?: boolean;
    max_candidates?: number;
  },
): Promise<MetadataEnrichmentJob> {
  const response = await fetch(`${API_BASE_URL}/admin/movies/${movieId}/enrichment/start`, {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify({
      source_language: options?.source_language ?? 'en-US',
      include_vi_localization: options?.include_vi_localization ?? true,
      max_candidates: options?.max_candidates ?? 5,
    }),
  });
  return handleResponse<MetadataEnrichmentJob>(response, 'Failed to start TMDB metadata enrichment');
}

export async function getMovieEnrichmentJobs(movieId: string): Promise<MetadataEnrichmentJob[]> {
  const response = await fetch(`${API_BASE_URL}/admin/movies/${movieId}/enrichment/jobs`, {
    method: 'GET',
    headers: authHeaders(false),
  });
  return handleResponse<MetadataEnrichmentJob[]>(response, 'Failed to load enrichment history');
}

export async function getEnrichmentJob(jobId: string): Promise<MetadataEnrichmentJob> {
  const response = await fetch(`${API_BASE_URL}/admin/enrichment/jobs/${jobId}`, {
    method: 'GET',
    headers: authHeaders(false),
  });
  return handleResponse<MetadataEnrichmentJob>(response, 'Failed to load enrichment job');
}

export async function selectEnrichmentCandidate(
  jobId: string,
  candidateId: string,
  notes?: string,
): Promise<MetadataEnrichmentJob> {
  const response = await fetch(`${API_BASE_URL}/admin/enrichment/jobs/${jobId}/select-candidate`, {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify({
      candidate_id: candidateId,
      notes: notes ?? null,
    }),
  });
  return handleResponse<MetadataEnrichmentJob>(response, 'Failed to select candidate');
}

export async function approveEnrichmentJob(
  jobId: string,
  payload: {
    candidate_id: string;
    approved_fields: string[];
    allow_overwrite_existing?: boolean;
    expected_metadata_version?: number | null;
    apply_immediately?: boolean;
    notes?: string;
  },
): Promise<MetadataEnrichmentJob> {
  const response = await fetch(`${API_BASE_URL}/admin/enrichment/jobs/${jobId}/approve`, {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify({
      candidate_id: payload.candidate_id,
      approved_fields: payload.approved_fields,
      allow_overwrite_existing: payload.allow_overwrite_existing ?? false,
      expected_metadata_version: payload.expected_metadata_version ?? null,
      apply_immediately: payload.apply_immediately ?? true,
      notes: payload.notes ?? null,
    }),
  });
  return handleResponse<MetadataEnrichmentJob>(response, 'Failed to approve and apply metadata');
}

export async function rejectEnrichmentJob(
  jobId: string,
  reason: string,
  candidateId?: string,
): Promise<MetadataEnrichmentJob> {
  const response = await fetch(`${API_BASE_URL}/admin/enrichment/jobs/${jobId}/reject`, {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify({
      reason,
      candidate_id: candidateId ?? null,
    }),
  });
  return handleResponse<MetadataEnrichmentJob>(response, 'Failed to reject enrichment job');
}

