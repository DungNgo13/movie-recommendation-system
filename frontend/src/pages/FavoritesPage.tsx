import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuthHook';
import { getToken } from '../services/authService';
import type { MovieListItem } from '../models';
import { useTranslation } from 'react-i18next';

import { API_BASE_URL } from '../config';

const FavoritesPage: React.FC = () => {
  const { user } = useAuth();
  const { favoriteIds, isFavorite, toggleFavorite } = useFavorites();
  const [movies, setMovies] = useState<MovieListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { t } = useTranslation(['movies', 'auth']);

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

  // Guest view: show count + login prompt if they have local favorites
  if (!user) {
    const guestCount = favoriteIds.length;
    return (
      <div className="favorites-page">
        <h1>{t("movies:favorites.title")}</h1>
        <div className="empty-state">
          {guestCount > 0 ? (
            <>
              <h3 className="empty-state__title">
                {guestCount !== 1 ? t("movies:favorites.guestSyncPlural", { count: guestCount }) : t("movies:favorites.guestSync", { count: guestCount })}
              </h3>
              <p className="empty-state__description">
                <Link to="/login">{t("auth:login.title", "Log in")}</Link> or{' '}
                <Link to="/register">{t("auth:register.title", "Register")}</Link>
                {t("movies:favorites.guestSyncDesc")}
              </p>
            </>
          ) : (
            <>
              <h3 className="empty-state__title">{t("movies:favorites.noFavorites")}</h3>
              <p className="empty-state__description">
                {t("movies:favorites.noFavoritesGuestDesc")}
                <Link to="/login">{t("auth:login.title", "Log in")}</Link>
              </p>
            </>
          )}
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
      <h1>{t("movies:favorites.title")}</h1>

      {displayedMovies.length === 0 ? (
        <div className="empty-state">
          <h3 className="empty-state__title">{t("movies:favorites.noFavorites")}</h3>
          <p className="empty-state__description">{t("movies:favorites.noFavoritesDesc")}</p>
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
