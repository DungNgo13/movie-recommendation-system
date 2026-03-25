import React from 'react';
import { Link } from 'react-router-dom';
import type { MovieListItem } from '../models';

interface MovieCardProps {
  movie: MovieListItem;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void;
}

const MovieCard: React.FC<MovieCardProps> = ({ movie, isFavorite, onToggleFavorite }) => {
  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleFavorite(movie.id);
  };

  return (
    <div className="movie-card">
      <button
        className={`favorite-btn${isFavorite ? ' favorite-btn--active' : ''}`}
        onClick={handleFavoriteClick}
        aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
        title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
      >
        {isFavorite ? '♥' : '♡'}
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
      </Link>
    </div>
  );
};

export default MovieCard;
