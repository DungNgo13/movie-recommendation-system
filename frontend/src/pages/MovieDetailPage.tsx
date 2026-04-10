import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import type { Movie } from '../models';
import { getMovieById } from '../services/movieService';
import { saveWatchProgress, getWatchProgress, recordWatch } from '../services/continueWatchingService';
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
// Save position every N seconds of playback change
const SAVE_INTERVAL_SECONDS = 15;
// Only prompt to resume if position is more than this many seconds in
const MIN_RESUME_SECONDS = 30;

const formatTime = (seconds: number): string => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
};

const MovieDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string>(PLACEHOLDER_IMAGE);
  const [myRating, setMyRating] = useState<number | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendedMovie[]>([]);

  // Resume state
  const [initialTime, setInitialTime] = useState<number>(0);
  const [savedPosition, setSavedPosition] = useState<number>(0);
  const [showResumePrompt, setShowResumePrompt] = useState(false);

  // Refs to track save throttle without causing re-renders
  const lastSavedTimeRef = useRef<number>(0);
  const lastDurationRef = useRef<number>(0);

  // Called by HlsPlayer on every timeupdate (~4Hz).
  // Throttled: only saves to backend every SAVE_INTERVAL_SECONDS.
  const handleTimeUpdate = (currentTime: number, duration: number) => {
    lastDurationRef.current = duration;
    if (!movie || !user) return;
    if (Math.abs(currentTime - lastSavedTimeRef.current) >= SAVE_INTERVAL_SECONDS) {
      lastSavedTimeRef.current = currentTime;
      saveWatchProgress(movie.id, currentTime, duration);
    }
  };

  // Save immediately on pause
  const handlePause = (currentTime: number, duration: number) => {
    if (!movie || !user || currentTime < 1) return;
    lastSavedTimeRef.current = currentTime;
    lastDurationRef.current = duration;
    saveWatchProgress(movie.id, currentTime, duration);
  };

  // Save as completed when video ends
  const handleEnded = (duration: number) => {
    if (!movie || !user) return;
    // Save at 100% — backend will mark is_completed = true
    saveWatchProgress(movie.id, duration, duration);
  };

  // Save on unmount (navigate away mid-watch)
  const movieRef = useRef<Movie | null>(null);
  movieRef.current = movie;
  const userRef = useRef(user);
  userRef.current = user;
  useEffect(() => {
    return () => {
      const pos = lastSavedTimeRef.current;
      const dur = lastDurationRef.current;
      if (movieRef.current && userRef.current && pos > 1 && dur > 0) {
        saveWatchProgress(movieRef.current.id, pos, dur);
      }
    };
  }, []);

  // Fetch recommendations
  useEffect(() => {
    if (!user) { setRecommendations([]); return; }
    getRecommendations(4).then(setRecommendations).catch(() => {});
  }, [user]);

  // Fetch movie + resume position
  useEffect(() => {
    const fetchMovie = async () => {
      if (!id) return;
      try {
        setLoading(true);
        setError(null);

        const data = await getMovieById(id);
        setMovie(data);
        setImageSrc(data.backdrop_url || data.poster_url || PLACEHOLDER_IMAGE);

        if (user) {
          try {
            const progress = await getWatchProgress(data.id);
            const pos = progress.current_time_seconds;
            if (pos >= MIN_RESUME_SECONDS && !progress.is_completed) {
              setSavedPosition(pos);
              setShowResumePrompt(true);
              // Don't set initialTime yet — wait for user choice
            }
          } catch {
            // Non-blocking
          }
        }

        // Record initial watch event (lightweight)
        recordWatch(data.id, 0);
      } catch {
        setError('Failed to fetch movie details.');
      } finally {
        setLoading(false);
      }
    };
    fetchMovie();
  }, [id, user]);

  // Rating
  useEffect(() => {
    if (!id || !user) { setMyRating(null); return; }
    getMyRating(id).then(setMyRating).catch(() => {});
  }, [id, user]);

  const handleRate = async (rating: number) => {
    if (!id || !user) return;
    try {
      await rateMovie(id, rating);
      setMyRating(rating);
    } catch { /* silently fail */ }
  };

  // Resume prompt actions
  const handleResume = () => {
    setInitialTime(savedPosition);
    lastSavedTimeRef.current = savedPosition;
    setShowResumePrompt(false);
  };

  const handleRestart = () => {
    setInitialTime(0);
    lastSavedTimeRef.current = 0;
    setShowResumePrompt(false);
  };

  const { isFavorite, toggleFavorite } = useFavorites();

  const handleImageError = () => {
    if (!movie) { setImageSrc(PLACEHOLDER_IMAGE); return; }
    const backdrop = movie.backdrop_url || '';
    const poster = movie.poster_url || '';
    if (imageSrc === backdrop && poster && poster !== backdrop) { setImageSrc(poster); return; }
    if (imageSrc !== PLACEHOLDER_IMAGE) setImageSrc(PLACEHOLDER_IMAGE);
  };

  if (loading) return <LoadingSpinner />;
  if (error)   return <ErrorMessage message={error} />;
  if (!movie)  return <div>Movie not found.</div>;

  return (
    <div className="movie-detail-page">

      {/* Resume prompt banner */}
      {showResumePrompt && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '1rem',
          padding: '0.75rem 1rem', marginBottom: '0.75rem',
          backgroundColor: '#1a3a5c', borderRadius: '8px',
          border: '1px solid #1565c0', color: '#90caf9',
          flexWrap: 'wrap',
        }}>
          <span>▶ Continue from <strong>{formatTime(savedPosition)}</strong>?</span>
          <button
            onClick={handleResume}
            style={{ padding: '0.3rem 0.9rem', background: '#1976d2', color: '#fff', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight: 600 }}
          >
            Resume
          </button>
          <button
            onClick={handleRestart}
            style={{ padding: '0.3rem 0.9rem', background: 'transparent', color: '#90caf9', border: '1px solid #1565c0', borderRadius: '5px', cursor: 'pointer' }}
          >
            Start over
          </button>
        </div>
      )}

      {movie.video_status === 'ready' && movie.hls_playlist_url ? (
        <HlsPlayer
          src={movie.hls_playlist_url}
          poster={imageSrc}
          initialTime={initialTime}
          onTimeUpdate={handleTimeUpdate}
          onPause={handlePause}
          onEnded={handleEnded}
        />
      ) : (
        <>
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
