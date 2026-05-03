import { getToken } from './authService';

import { API_BASE_URL } from '../config';

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
}

// ─── Types mirroring the backend payload ─────────────────────────────────────

export interface SignalEntry {
  movie_id: string;
  movie_title: string;
  signal_type: 'rating' | 'favorite' | 'watch';
  raw_value: number | string;
  calculated_weight: number;
  weight_breakdown: string;
}

export interface WeightSummary {
  total_signals: number;
  unique_movies_in_profile: number;
  highest_weight_movie: string | null;
  highest_weight_value: number | null;
}

export interface RecommendationEntry {
  rank: number;
  movie_id: string;
  movie_title: string;
  genres: string[];
  cast: string[];
  keywords: string[];
  director: string | null;
  release_year: number | null;
  poster_url: string | null;
  total_score: number;
  score_interpretation: string;
  contributing_factors: string[];
}

export interface ExplainPayload {
  user_id: string;
  user_email: string;
  algorithm_version: string;
  is_cold_start: boolean;
  cold_start_reason?: string;
  algorithm_summary?: string;
  user_context: SignalEntry[];
  weight_summary?: WeightSummary;
  top_recommendations: RecommendationEntry[];
}

// ─── API call ─────────────────────────────────────────────────────────────────

export const explainRecommendations = async (
  userId: string,
  topN: number = 10
): Promise<ExplainPayload> => {
  const res = await fetch(
    `${API_BASE_URL}/admin/recommendations/explain/${userId}?top_n=${topN}`,
    { headers: authHeaders() }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Request failed: ${res.status}`);
  }
  return res.json();
};
