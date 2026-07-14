import React from 'react';
import { Link } from 'react-router-dom';
import HeartIcon from './HeartIcon';
import type { RecommendedMovie } from '../services/recommendationService';

interface RecommendationCardProps {
  movie: RecommendedMovie;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void | Promise<void>;
  favoriteLoading?: boolean;
}

/** True when this recommendation came from the cold-start fallback. */
const isColdStart = (movie: RecommendedMovie): boolean =>
  movie.score === 0 || (movie.reason ?? '').toLowerCase().includes('popular movie');

const RecommendationCard: React.FC<RecommendationCardProps> = ({
  movie,
  isFavorite,
  onToggleFavorite,
  favoriteLoading = false,
}) => {
  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (favoriteLoading) return;
    onToggleFavorite(movie.id);
  };

  const coldStart = isColdStart(movie);

  const favoriteLabel = isFavorite
    ? `Remove ${movie.title} from favorites`
    : `Add ${movie.title} to favorites`;

  return (
    <div className="movie-card rec-card">
      <Link to={`/movie/${movie.id}`}>
        <div style={{ position: 'relative', width: '100%', aspectRatio: '2/3', background: '#1e1e22' }}>
          <img
            src={movie.poster_url || '/placeholder-poster.svg'}
            alt={`${movie.title} poster`}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = '/placeholder-poster.svg';
            }}
          />
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
        <p className="rec-reason">{movie.reason}</p>
        <span className="rec-score">
          {coldStart ? 'New for you' : `${Math.round(movie.score * 100)}% match`}
        </span>
      </Link>
    </div>
  );
};

export default RecommendationCard;
