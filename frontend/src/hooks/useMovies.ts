import { useState, useEffect } from 'react';
import type { MovieListItem } from '../models';
import { getMovies } from '../services/movieService';
import type { MovieFilters } from '../services/movieService';

export interface UseMoviesResult {
  movies: MovieListItem[];
  total: number;
  page: number;
  limit: number;
  loading: boolean;
  error: string | null;
}

export const useMovies = (
  page = 1,
  limit = 20,
  filters?: MovieFilters,
): UseMoviesResult => {
  const [movies, setMovies] = useState<MovieListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchMovies = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getMovies(page, limit, filters);
        if (!cancelled) {
          setMovies(data.items);
          setTotal(data.total);
        }
      } catch (err) {
        if (!cancelled) {
          setError('Failed to fetch movies');
          console.error(err);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchMovies();

    return () => {
      cancelled = true;
    };
    // Serialize filters to a stable string so useEffect re-fires only on value changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, limit, filters?.search, filters?.genre, filters?.year]);

  return { movies, total, page, limit, loading, error };
};
