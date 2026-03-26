import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { Movie } from '../models';
import { getMovieById } from '../services/movieService';
import { recordWatch } from '../services/continueWatchingService';
import { getMyRating, rateMovie } from '../services/ratingService';
import { useRecommendations } from '../hooks/useRecommendations';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import MovieCard from '../components/MovieCard';
import StarRating from '../components/StarRating';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const PLACEHOLDER_IMAGE = '/placeholder-poster.svg';

const MovieDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string>(PLACEHOLDER_IMAGE);
  const [myRating, setMyRating] = useState<number | null>(null);

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

        // Record watch history via API (fire-and-forget)
        recordWatch(data.id);
      } catch (err) {
        setError('Failed to fetch movie details.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMovie();
  }, [id]);

  // Fetch user's existing rating for this movie
  useEffect(() => {
    if (!id || !user) {
      setMyRating(null);
      return;
    }
    const fetchRating = async () => {
      const rating = await getMyRating(id);
      setMyRating(rating);
    };
    fetchRating();
  }, [id, user]);

  const handleRate = async (rating: number) => {
    if (!id || !user) return;
    try {
      await rateMovie(id, rating);
      setMyRating(rating);
    } catch {
      // silently fail
    }
  };

  // Compute release year for recommendations hook
  const releaseYear = movie?.release_date
    ? (() => { const y = new Date(movie.release_date).getFullYear(); return Number.isNaN(y) ? null : y; })()
    : null;

  const { recommendations } = useRecommendations(id, movie?.title ?? '', releaseYear);
  const { isFavorite, toggleFavorite } = useFavorites();

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

      <div className="rating-section">
        <h3>Your Rating</h3>
        {user ? (
          <>
            <StarRating currentRating={myRating} onRate={handleRate} />
            {myRating && <span className="rating-label">{myRating}/5</span>}
          </>
        ) : (
          <p className="rating-login-hint">Login to rate this movie</p>
        )}
      </div>

      {recommendations.length > 0 && (
        <section className="recommendations-section">
          <h2>Recommended Movies</h2>
          <div className="movie-list">
            {recommendations.map((rec) => (
              <MovieCard
                key={rec.id}
                movie={rec}
                isFavorite={isFavorite(rec.id)}
                onToggleFavorite={toggleFavorite}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default MovieDetailPage;
