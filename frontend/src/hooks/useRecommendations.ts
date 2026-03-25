import { useState, useEffect } from 'react';
import type { MovieListItem } from '../models';
import { getMovies } from '../services/movieService';
import { getRecommendations } from '../utils/recommendation';

/**
 * Custom hook that fetches the movie list and computes recommendations
 * for a given movie based on title keyword matching and release year proximity.
 */
export const useRecommendations = (
  movieId: string | undefined,
  title: string,
  releaseYear: number | null,
) => {
  const [recommendations, setRecommendations] = useState<MovieListItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!movieId) return;

    let cancelled = false;

    const fetchAndCompute = async () => {
      try {
        setLoading(true);
        const data = await getMovies(1, 100);
        if (cancelled) return;

        const results = getRecommendations(
          movieId,
          title,
          releaseYear,
          data.items,
        );
        setRecommendations(results);
      } catch {
        // Silently fail — recommendations are non-critical
        setRecommendations([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchAndCompute();

    return () => {
      cancelled = true;
    };
  }, [movieId, title, releaseYear]);

  return { recommendations, loading };
};
