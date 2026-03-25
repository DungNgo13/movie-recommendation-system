import React, { useState, useEffect, useMemo } from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useFavorites } from '../hooks/useFavorites';
import { getMovies } from '../services/movieService';
import type { MovieListItem } from '../models';

const FavoritesPage: React.FC = () => {
  const { favoriteIds, isFavorite, toggleFavorite } = useFavorites();
  const [allMovies, setAllMovies] = useState<MovieListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMovies = async () => {
      try {
        setLoading(true);
        const data = await getMovies(1, 100);
        setAllMovies(data.items);
      } catch {
        setError('Failed to fetch movies.');
      } finally {
        setLoading(false);
      }
    };

    fetchMovies();
  }, []);

  const favoriteMovies = useMemo(
    () => allMovies.filter((m) => favoriteIds.includes(m.id)),
    [allMovies, favoriteIds],
  );

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="favorites-page">
      <h1>♥ My Favorites</h1>

      {favoriteMovies.length === 0 ? (
        <p className="no-results">No favorite movies yet.</p>
      ) : (
        <div className="movie-list">
          {favoriteMovies.map((movie) => (
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
