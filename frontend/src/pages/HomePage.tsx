import React from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useMovies } from '../hooks/useMovies';
import { useFavorites } from '../hooks/useFavorites';

const HomePage: React.FC = () => {
  const { movies, loading, error } = useMovies();
  const { isFavorite, toggleFavorite } = useFavorites();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="home-page">
      <h1>Movies</h1>
      <div className="movie-list">
        {movies.map((movie) => (
          <MovieCard
            key={movie.id}
            movie={movie}
            isFavorite={isFavorite(movie.id)}
            onToggleFavorite={toggleFavorite}
          />
        ))}
      </div>
    </div>
  );
};

export default HomePage;
