import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import type { Movie } from '../models';
import { getMovieById } from '../services/movieService';
import { recordWatch, getWatchStatus } from '../services/continueWatchingService';
import { getMyRating, rateMovie } from '../services/ratingService';
import { getRecommendations } from '../services/recommendationService';
import type { RecommendedMovie } from '../services/recommendationService';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import RecommendationCard from '../components/RecommendationCard';
import StarRating from '../components/StarRating';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import HlsPlayer from '../components/HlsPlayer';

const PLACEHOLDER_IMAGE = '/placeholder-poster.svg';

const MovieDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string>(PLACEHOLDER_IMAGE);
  const [myRating, setMyRating] = useState<number | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendedMovie[]>([]);
  const [initialTime, setInitialTime] = useState<number>(0);
  const lastSavedTime = useRef<number>(0);

  const handleTimeUpdate = (currentTime: number) => {
    if (Math.abs(currentTime - lastSavedTime.current) >= 15) {
      lastSavedTime.current = currentTime;
      if (movie) {
        recordWatch(movie.id, currentTime);
      }
    }
  };

  useEffect(() => {
    if (!user) {
      setRecommendations([]);
      return;
    }
    const fetchRecs = async () => {
      const recs = await getRecommendations(4);
      setRecommendations(recs);
    };
    fetchRecs();
  }, [user]);

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

        if (user) {
          try {
            const status = await getWatchStatus(data.id);
            if (status?.playback_position_seconds > 0) {
              setInitialTime(status.playback_position_seconds);
              lastSavedTime.current = status.playback_position_seconds;
            }
          } catch (e) {
            console.error('Failed to parse previous watch position:', e);
          }
        }

        // Record initial watch history hook conservatively explicitly dynamically
        recordWatch(data.id, 0);
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
      {movie.video_status === 'ready' && movie.hls_playlist_url ? (
        <HlsPlayer 
          src={movie.hls_playlist_url} 
          poster={imageSrc} 
          initialTime={initialTime}
          onTimeUpdate={handleTimeUpdate}
        />
      ) : (
      <>
          {/* Cinema-style banner: blurred background + properly contained foreground image.
              Works for both portrait and landscape uploads without severe cropping. */}
          <div className="movie-banner">
            <div
              className="movie-banner__bg"
              style={{ backgroundImage: `url(${imageSrc})` }}
              aria-hidden="true"
            />
            <img
              src={imageSrc}
              alt={`${movie.title} backdrop`}
              onError={handleImageError}
              className="movie-banner__img"
            />
          </div>
          {movie.video_status === 'processing' && (
            <div style={{ padding: '1rem', marginTop: '1rem', backgroundColor: '#19426b', color: '#90caf9', borderRadius: '6px', border: '1px solid #1565c0' }}>
              <strong>Processing:</strong> High-Definition video is currently being generated. Check back shortly!
            </div>
          )}
          {movie.video_status === 'failed' && (
            <div style={{ padding: '1rem', marginTop: '1rem', backgroundColor: '#5c1616', color: '#ef9a9a', borderRadius: '6px', border: '1px solid #c62828' }}>
              <strong>Error:</strong>{' '}
              {movie.processing_error ?? 'Video stream conversion failed. Please contact an administrator.'}
            </div>
          )}
        </>
      )}

      <h1>{movie.title}</h1>
      <p>{movie.overview}</p>
      <p>Release Year: {movie.release_date ? movie.release_date.split('-')[0] : 'N/A'}</p>
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
          <h2>🤖 Recommended for You</h2>
          <div className="movie-list">
            {recommendations.map((rec) => (
              <RecommendationCard
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
