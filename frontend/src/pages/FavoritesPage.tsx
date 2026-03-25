import React, { useState, useEffect } from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import { getToken } from '../services/authService';
import type { MovieListItem } from '../models';

const API_BASE_URL = 'http://localhost:8000/api/v1';

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
        <p className="no-results">Please login to see your favorites.</p>
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
        <p className="no-results">No favorite movies yet.</p>
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
