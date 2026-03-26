import { getToken } from './authService';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface RecommendedMovie {
  id: string;
  title: string;
  poster_url: string | null;
  release_year: number | null;
  score: number;
  reason: string;
}

/**
 * Fetch personalized recommendations for the current user.
 * Returns empty array if not logged in.
 */
export const getRecommendations = async (topN = 10): Promise<RecommendedMovie[]> => {
  const token = getToken();
  if (!token) return [];

  const response = await fetch(`${API_BASE_URL}/recommendations/me?top_n=${topN}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return [];
  return response.json();
};
