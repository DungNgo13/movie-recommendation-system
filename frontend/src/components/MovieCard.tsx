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
        {isFavorite ? 'Saved' : 'Save'}
      </button>
      <Link to={`/movie/${movie.id}`}>
        <div style={{ position: 'relative', width: '100%', aspectRatio: '2/3', background: '#1e1e22' }}>
          {/* Primary Poster */}
          <img
            src={movie.poster_url || '/placeholder-poster.svg'}
            alt={`${movie.title} poster`}
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
              alt={`${movie.title} backdrop`}
              style={{ 
                position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover',
                opacity: showBackdrop ? 1 : 0, transition: 'opacity 0.6s ease-in-out' 
              }}
            />
          )}
        </div>
        <h3>{movie.title}</h3>
      </Link>
    </div>
  );
};

export default MovieCard;
