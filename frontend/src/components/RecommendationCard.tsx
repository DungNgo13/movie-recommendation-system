import React from 'react';
import { Link } from 'react-router-dom';
import type { RecommendedMovie } from '../services/recommendationService';

interface RecommendationCardProps {
  movie: RecommendedMovie;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void | Promise<void>;
}

/** True when this recommendation came from the cold-start fallback. */
const isColdStart = (movie: RecommendedMovie): boolean =>
  movie.score === 0 || (movie.reason ?? '').toLowerCase().includes('popular movie');

const RecommendationCard: React.FC<RecommendationCardProps> = ({
  movie,
  isFavorite,
  onToggleFavorite,
}) => {
  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleFavorite(movie.id);
  };

  const coldStart = isColdStart(movie);

  return (
    <div className="movie-card rec-card">
      <button
        className={`favorite-btn${isFavorite ? ' favorite-btn--active' : ''}`}
        onClick={handleFavoriteClick}
        aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
        title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
      >
        {isFavorite ? 'Favorited' : 'Favorite'}
      </button>
      <Link to={`/movie/${movie.id}`}>
        <img
          src={movie.poster_url || '/placeholder-poster.svg'}
          alt={`${movie.title} poster`}
          onError={(e) => {
            e.currentTarget.onerror = null;
            e.currentTarget.src = '/placeholder-poster.svg';
          }}
        />
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

