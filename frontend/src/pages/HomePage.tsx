import React from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useMovies } from '../hooks/useMovies';

const HomePage: React.FC = () => {
  const { movies, loading, error, debugData } = useMovies();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="home-page">
      {/* Debugging section */}
      <pre style={{ textAlign: 'left', backgroundColor: '#f0f0f0', padding: '10px' }}>
        {JSON.stringify(debugData, null, 2)}
      </pre>
      
      <h1>Movies</h1>
      <div className="movie-list">
        {movies.map((movie) => (
          <MovieCard key={movie.id} movie={movie} />
        ))}
      </div>
    </div>
  );
};

export default HomePage;
