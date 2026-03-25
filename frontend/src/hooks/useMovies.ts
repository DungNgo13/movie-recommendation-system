import { useState, useEffect } from 'react';
import type { MovieListItem, PaginatedMovies } from '../models';
import { getMovies } from '../services/movieService';

export const useMovies = () => {
  const [movies, setMovies] = useState<MovieListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [debugData, setDebugData] = useState<PaginatedMovies | null>(null); // For debugging

  useEffect(() => {
    const fetchMovies = async () => {
      try {
        setLoading(true);
        const data = await getMovies();
        setDebugData(data); // Store raw data
        setMovies(data.items);
      } catch (err) {
        setError('Failed to fetch movies');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMovies();
  }, []);

  return { movies, loading, error, debugData };
};
