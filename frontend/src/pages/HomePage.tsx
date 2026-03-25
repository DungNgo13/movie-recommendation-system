import React from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useMovies } from '../hooks/useMovies';
import { useFavorites } from '../hooks/useFavorites';
import { getContinueWatchingMovie } from '../services/continueWatchingService';

const HomePage: React.FC = () => {
  const { movies, loading, error } = useMovies();
  const { isFavorite, toggleFavorite } = useFavorites();
  const continueWatchingMovie = getContinueWatchingMovie();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="home-page">
      {continueWatchingMovie && (
        <section className="continue-watching-section">
          <h2>Continue Watching</h2>
          <div className="movie-list">
            <MovieCard
              movie={continueWatchingMovie}
              isFavorite={isFavorite(continueWatchingMovie.id)}
              onToggleFavorite={toggleFavorite}
            />
          </div>
        </section>
      )}

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
