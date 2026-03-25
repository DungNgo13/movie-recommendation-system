import { useState, useCallback } from 'react';
import {
  getFavoriteMovieIds,
  toggleFavoriteMovie,
} from '../services/favoriteService';

/**
 * Custom hook to manage favorite movies state.
 * Initializes from localStorage and keeps React state in sync.
 */
export const useFavorites = () => {
  const [favoriteIds, setFavoriteIds] = useState<string[]>(getFavoriteMovieIds);

  const isFavorite = useCallback(
    (id: string): boolean => favoriteIds.includes(id),
    [favoriteIds],
  );

  const toggleFavorite = useCallback((id: string): void => {
    const updated = toggleFavoriteMovie(id);
    setFavoriteIds(updated);
  }, []);

  return { favoriteIds, isFavorite, toggleFavorite };
};
