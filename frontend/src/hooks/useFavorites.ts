import { useState, useEffect, useCallback } from 'react';
import { useAuth } from './useAuthHook';
import {
  getFavoriteMovieIds,
  addFavoriteMovie,
  removeFavoriteMovie,
  getGuestFavoriteIds,
  addGuestFavorite,
  removeGuestFavorite,
} from '../services/favoriteService';

/**
 * Custom hook to manage favorite movies state.
 *
 * - Authenticated users: reads/writes via API (existing behavior).
 * - Guest users: reads/writes via localStorage so guests can mark
 *   favorites before logging in.  Guest data is merged server-side
 *   at login time and then cleared from localStorage.
 */
export const useFavorites = () => {
  const { user } = useAuth();
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      // Authenticated: fetch from server
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
    } else {
      // Guest: load from localStorage
      setFavoriteIds(getGuestFavoriteIds());
    }
  }, [user]);

  const isFavorite = useCallback(
    (id: string): boolean => favoriteIds.includes(id),
    [favoriteIds],
  );

  const toggleFavorite = useCallback(async (id: string): Promise<void> => {
    if (user) {
      // ── Authenticated toggle (API) ──
      if (favoriteIds.includes(id)) {
        // Optimistic remove
        setFavoriteIds((prev) => prev.filter((fid) => fid !== id));
        try {
          await removeFavoriteMovie(id);
        } catch {
          // Revert on error
          setFavoriteIds((prev) => [...prev, id]);
        }
      } else {
        // Optimistic add
        setFavoriteIds((prev) => [...prev, id]);
        try {
          await addFavoriteMovie(id);
        } catch {
          setFavoriteIds((prev) => prev.filter((fid) => fid !== id));
        }
      }
    } else {
      // ── Guest toggle (localStorage) ──
      if (favoriteIds.includes(id)) {
        removeGuestFavorite(id);
        setFavoriteIds((prev) => prev.filter((fid) => fid !== id));
      } else {
        addGuestFavorite(id);
        setFavoriteIds((prev) => [...prev, id]);
      }
    }
  }, [user, favoriteIds]);

  return { favoriteIds, isFavorite, toggleFavorite, loading };
};
