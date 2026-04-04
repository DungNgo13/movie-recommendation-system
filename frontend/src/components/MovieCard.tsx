import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { MovieListItem } from '../models';

interface MovieCardProps {
  movie: Pick<MovieListItem, 'id' | 'title' | 'poster_url' | 'backdrop_url'>;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void | Promise<void>;
  enableImageSwap?: boolean;
}

const MovieCard: React.FC<MovieCardProps> = ({ movie, isFavorite, onToggleFavorite, enableImageSwap = false }) => {
  const [showBackdrop, setShowBackdrop] = useState(false);

  useEffect(() => {
    let interval: number;
    if (enableImageSwap && movie.backdrop_url) {
      interval = window.setInterval(() => {
        setShowBackdrop((prev) => !prev);
      }, 4000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [enableImageSwap, movie.backdrop_url]);

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleFavorite(movie.id);
  };

  const currentImage = (showBackdrop && movie.backdrop_url) ? movie.backdrop_url : (movie.poster_url || '/placeholder-poster.svg');

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
          src={currentImage}
          alt={`${movie.title} poster`}
          style={{ transition: 'opacity 0.5s ease-in-out' }}
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
