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
        <img src={movie.poster_url || ''} alt={`${movie.title} poster`} />
        <h3>{movie.title}</h3>
      </Link>
    </div>
  );
};

export default MovieCard;
