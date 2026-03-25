import { useState, useEffect, useCallback } from 'react';
import { useAuth } from './useAuth';
import {
  getFavoriteMovieIds,
  addFavoriteMovie,
  removeFavoriteMovie,
} from '../services/favoriteService';

/**
 * Custom hook to manage favorite movies state via API.
 * Returns empty state if user is not logged in.
 */
export const useFavorites = () => {
  const { user } = useAuth();
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) {
      setFavoriteIds([]);
      return;
    }
    let cancelled = false;
    const fetchIds = async () => {
      setLoading(true);
      try {
        const ids = await getFavoriteMovieIds();
        if (!cancelled) setFavoriteIds(ids);
      } catch {
        if (!cancelled) setFavoriteIds([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchIds();
    return () => { cancelled = true; };
  }, [user]);

  const isFavorite = useCallback(
    (id: string): boolean => favoriteIds.includes(id),
    [favoriteIds],
  );

  const toggleFavorite = useCallback(async (id: string): Promise<void> => {
    if (!user) return;

    if (favoriteIds.includes(id)) {
      // Optimistic update
      setFavoriteIds((prev) => prev.filter((fid) => fid !== id));
      try {
        await removeFavoriteMovie(id);
      } catch {
        // Revert on error
        setFavoriteIds((prev) => [...prev, id]);
      }
    } else {
      setFavoriteIds((prev) => [...prev, id]);
      try {
        await addFavoriteMovie(id);
      } catch {
        setFavoriteIds((prev) => prev.filter((fid) => fid !== id));
      }
    }
  }, [user, favoriteIds]);

  return { favoriteIds, isFavorite, toggleFavorite, loading };
};
