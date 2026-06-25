import React, { useState, useEffect } from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import { getToken } from '../services/authService';
import type { MovieListItem } from '../models';

import { API_BASE_URL } from '../config';

const FavoritesPage: React.FC = () => {
  const { user } = useAuth();
  const { isFavorite, toggleFavorite } = useFavorites();
  const [movies, setMovies] = useState<MovieListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setMovies([]);
      setLoading(false);
      return;
    }

    const fetchFavorites = async () => {
      try {
        setLoading(true);
        const token = getToken();
        const response = await fetch(`${API_BASE_URL}/favorites/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch favorites');
        const data: MovieListItem[] = await response.json();
        setMovies(data);
      } catch {
        setError('Failed to fetch favorite movies.');
      } finally {
        setLoading(false);
      }
    };

    fetchFavorites();
  }, [user]);

  // Remove unfavorited movies from list reactively
  const displayedMovies = movies.filter((m) => isFavorite(m.id));

  if (!user) {
    return (
      <div className="favorites-page">
        <h1>♥ My Favorites</h1>
        <div className="empty-state">
          <span className="empty-state__icon">🔒</span>
          <h3 className="empty-state__title">Login required</h3>
          <p className="empty-state__description">Please login to see your favorite movies.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="favorites-page">
      <h1>♥ My Favorites</h1>

      {displayedMovies.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__icon">♡</span>
          <h3 className="empty-state__title">No favorites yet</h3>
          <p className="empty-state__description">Browse movies and click the heart icon to save your favorites here.</p>
        </div>
      ) : (
        <div className="movie-list">
          {displayedMovies.map((movie) => (
            <MovieCard
              key={movie.id}
              movie={movie}
              isFavorite={isFavorite(movie.id)}
              onToggleFavorite={toggleFavorite}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default FavoritesPage;
