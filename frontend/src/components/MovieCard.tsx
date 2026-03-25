import React from 'react';
import { Link } from 'react-router-dom';
import type { MovieListItem } from '../models';

interface MovieCardProps {
  movie: MovieListItem;
}

const MovieCard: React.FC<MovieCardProps> = ({ movie }) => {
  return (
    <div className="movie-card">
      <Link to={`/movie/${movie.id}`}>
        <img
          src={movie.poster_url || '/placeholder-poster.svg'}
          alt={`${movie.title} poster`}
          onError={(e) => {
            e.currentTarget.onerror = null; // Prevent infinite loop if placeholder fails
            e.currentTarget.src = '/placeholder-poster.svg';
          }}
        />
        <h3>{movie.title}</h3>
      </Link>
    </div>
  );
};

export default MovieCard;
