import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { Movie } from '../models';
import { getMovieById } from '../services/movieService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const MovieDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMovie = async () => {
      if (!id) return;
      try {
        setLoading(true);
        const data = await getMovieById(id);
        setMovie(data);
      } catch (err) {
        setError('Failed to fetch movie details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMovie();
  }, [id]);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  if (!movie) {
    return <div>Movie not found.</div>;
  }

  return (
    <div className="movie-detail-page">
      <img src={movie.backdrop_url || ''} alt={`${movie.title} backdrop`} />
      <h1>{movie.title}</h1>
      <p>{movie.overview}</p>
      <p>Release Date: {movie.release_date}</p>
      <p>Director: {movie.director}</p>
      {/* Add more details as needed */}
    </div>
  );
};

export default MovieDetailPage;
