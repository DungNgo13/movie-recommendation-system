import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { Movie } from '../models';
import { getMovieById } from '../services/movieService';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const PLACEHOLDER_IMAGE = '/placeholder-poster.svg';

const MovieDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string>(PLACEHOLDER_IMAGE);

  useEffect(() => {
    const fetchMovie = async () => {
      if (!id) return;

      try {
        setLoading(true);
        setError(null);

        const data = await getMovieById(id);
        setMovie(data);

        setImageSrc(
          data.backdrop_url || data.poster_url || PLACEHOLDER_IMAGE
        );
      } catch (err) {
        setError('Failed to fetch movie details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMovie();
  }, [id]);

  const handleImageError = () => {
    if (!movie) {
      setImageSrc(PLACEHOLDER_IMAGE);
      return;
    }

    const backdrop = movie.backdrop_url || '';
    const poster = movie.poster_url || '';

    if (imageSrc === backdrop && poster && poster !== backdrop) {
      setImageSrc(poster);
      return;
    }

    if (imageSrc !== PLACEHOLDER_IMAGE) {
      setImageSrc(PLACEHOLDER_IMAGE);
    }
  };

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
      <img
        src={imageSrc}
        alt={`${movie.title} backdrop`}
        onError={handleImageError}
      />
      <h1>{movie.title}</h1>
      <p>{movie.overview}</p>
      <p>Release Date: {movie.release_date}</p>
      <p>Director: {movie.director}</p>
    </div>
  );
};

export default MovieDetailPage;
