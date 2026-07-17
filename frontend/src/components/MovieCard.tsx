import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import HeartIcon from './HeartIcon';
import type { MovieListItem } from '../models';
import { useTranslation } from 'react-i18next';
import { getLocalizedTitle } from '../utils/localizedMovie';

interface MovieCardProps {
  movie: Pick<MovieListItem, 'id' | 'title' | 'title_vi' | 'poster_url' | 'backdrop_url'>;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void | Promise<void>;
  favoriteLoading?: boolean;
  enableImageSwap?: boolean;
}

const MovieCard: React.FC<MovieCardProps> = ({ movie, isFavorite, onToggleFavorite, favoriteLoading = false, enableImageSwap = false }) => {
  const [showBackdrop, setShowBackdrop] = useState(false);
  const { i18n } = useTranslation();
  const localizedTitle = getLocalizedTitle(movie, i18n.language as any);

  useEffect(() => {
    let interval: number;
    if (enableImageSwap && movie.backdrop_url) {
      // Random duration per card so all cards don't swap in perfect sync.
      // Computed once at mount; range: 3000 – 5000 ms.
      const swapInterval = Math.floor(Math.random() * 2000) + 3000;
      interval = window.setInterval(() => {
        setShowBackdrop((prev) => !prev);
      }, swapInterval);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [enableImageSwap, movie.backdrop_url]);

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (favoriteLoading) return;
    onToggleFavorite(movie.id);
  };

  const favoriteLabel = isFavorite
    ? `Remove ${localizedTitle} from favorites`
    : `Add ${localizedTitle} to favorites`;

  return (
    <div className="movie-card">
      <Link to={`/movie/${movie.id}`}>
        <div style={{ position: 'relative', width: '100%', aspectRatio: '2/3', background: '#1e1e22' }}>
          {/* Primary Poster */}
          <img
            src={movie.poster_url || '/placeholder-poster.svg'}
            alt={`${localizedTitle} poster`}
            style={{ 
              position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover',
              opacity: showBackdrop ? 0 : 1, transition: 'opacity 0.6s ease-in-out' 
            }}
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = '/placeholder-poster.svg';
            }}
          />
          {/* Secondary Backdrop */}
          {enableImageSwap && movie.backdrop_url && (
            <img
              src={movie.backdrop_url}
              alt={`${localizedTitle} backdrop`}
              style={{ 
                position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover',
                opacity: showBackdrop ? 1 : 0, transition: 'opacity 0.6s ease-in-out' 
              }}
            />
          )}
          {/* Favorite Heart Button — inside poster area so it stays positioned correctly */}
          <button
            type="button"
            className={`movie-card__favorite-button${isFavorite ? ' movie-card__favorite-button--active' : ''}`}
            onClick={handleFavoriteClick}
            disabled={favoriteLoading}
            aria-label={favoriteLabel}
            title={favoriteLabel}
          >
            <HeartIcon filled={isFavorite} className="movie-card__favorite-icon" />
          </button>
        </div>
        <h3>{movie.title}</h3>
      </Link>
    </div>
  );
};

export default MovieCard;
