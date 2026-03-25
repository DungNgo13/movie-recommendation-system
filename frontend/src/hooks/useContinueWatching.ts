import { useState, useCallback } from 'react';
import type { MovieListItem } from '../models';
import {
  getContinueWatchingMovie,
  setContinueWatchingMovie as saveToStorage,
} from '../services/continueWatchingService';

/**
 * Custom hook to manage the continue-watching movie state.
 * Initializes from localStorage and keeps React state in sync.
 */
export const useContinueWatching = () => {
  const [continueWatchingMovie, setContinueWatchingMovie] =
    useState<MovieListItem | null>(getContinueWatchingMovie);

  const saveMovie = useCallback((movie: MovieListItem): void => {
    saveToStorage(movie);
    setContinueWatchingMovie(movie);
  }, []);

  return { continueWatchingMovie, saveMovie };
};
