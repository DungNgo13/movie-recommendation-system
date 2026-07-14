import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import type { Movie, MovieAsset } from '../models';
import { getMovieById } from '../services/movieService';
import { API_BASE_URL, resolveMediaUrl } from '../config';
import {
  saveWatchProgress,
  getWatchProgress,
  saveGuestWatchProgress,
  getGuestWatchProgressForMovie,
} from '../services/continueWatchingService';
import { getMyRating, rateMovie } from '../services/ratingService';
import { getRecommendations } from '../services/recommendationService';
import type { RecommendedMovie } from '../services/recommendationService';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuthHook';
import RecommendationCard from '../components/RecommendationCard';
import StarRating from '../components/StarRating';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import HlsPlayer from '../components/HlsPlayer';
import SourceAttribution from '../components/SourceAttribution';

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
  const [assets, setAssets] = useState<MovieAsset[]>([]);

  // Resume state
  const [initialTime, setInitialTime] = useState<number>(0);
  const [savedPosition, setSavedPosition] = useState<number>(0);
  const [showResumePrompt, setShowResumePrompt] = useState(false);

  // Refs to track save throttle without causing re-renders
  const lastSavedTimeRef = useRef<number>(0);
  const lastDurationRef = useRef<number>(0);

  // Called by HlsPlayer on every timeupdate (~4Hz).
  // Throttled: only saves to backend every SAVE_INTERVAL_SECONDS.
  // Falls through to guest localStorage save when no user is authenticated.
  const handleTimeUpdate = (currentTime: number, duration: number) => {
    if (!Number.isFinite(currentTime) || !Number.isFinite(duration) || duration <= 0) return;
    lastDurationRef.current = duration;
    if (!movie) return;
    if (Math.abs(currentTime - lastSavedTimeRef.current) >= SAVE_INTERVAL_SECONDS) {
      lastSavedTimeRef.current = currentTime;
      if (user) {
        saveWatchProgress(movie.id, currentTime, duration);
      } else {
        saveGuestWatchProgress(movie.id, currentTime, duration);
      }
    }
  };

  // Save immediately on pause
  const handlePause = (currentTime: number, duration: number) => {
    if (!movie || currentTime < 1) return;
    if (!Number.isFinite(currentTime) || !Number.isFinite(duration) || duration <= 0) return;
    lastSavedTimeRef.current = currentTime;
    lastDurationRef.current = duration;
    if (user) {
      saveWatchProgress(movie.id, currentTime, duration);
    } else {
      saveGuestWatchProgress(movie.id, currentTime, duration);
    }
  };

  // Save as completed when video ends
  const handleEnded = (duration: number) => {
    if (!movie) return;
    if (!Number.isFinite(duration) || duration <= 0) return;
    // Save at 100% — backend will mark is_completed = true
    if (user) {
      saveWatchProgress(movie.id, duration, duration);
    } else {
      saveGuestWatchProgress(movie.id, duration, duration);
    }
  };

  // Save on unmount (navigate away mid-watch)
  const movieRef = useRef<Movie | null>(null);
  movieRef.current = movie;
  const userRef = useRef(user);
  userRef.current = user;

  /** Shared helper — saves current progress from refs. */
  const saveProgressFromRefs = () => {
    const pos = lastSavedTimeRef.current;
    const dur = lastDurationRef.current;
    if (movieRef.current && Number.isFinite(pos) && Number.isFinite(dur) && pos > 1 && dur > 0) {
      if (userRef.current) {
        saveWatchProgress(movieRef.current.id, pos, dur);
      } else {
        saveGuestWatchProgress(movieRef.current.id, pos, dur);
      }
    }
  };

  // Save on: unmount, visibilitychange (tab hidden), beforeunload (page close)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveProgressFromRefs();
      }
    };
    const handleBeforeUnload = () => {
      saveProgressFromRefs();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Final save on component unmount (route change)
      saveProgressFromRefs();
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
        setImageSrc(resolveMediaUrl(data.backdrop_url) || resolveMediaUrl(data.poster_url) || PLACEHOLDER_IMAGE);

        // Fetch per-asset license data
        try {
          const assetRes = await fetch(`${API_BASE_URL}/movies/${id}/assets`);
          if (assetRes.ok) {
            const assetData = await assetRes.json();
            setAssets(assetData.items || []);
            // Use asset poster/backdrop if available and not blocked/unknown
            const posterAsset = (assetData.items || []).find(
              (a: MovieAsset) => a.asset_type === 'poster' && a.media_rights_status !== 'blocked' && a.media_rights_status !== 'unknown' && a.url
            );
            const backdropAsset = (assetData.items || []).find(
              (a: MovieAsset) => a.asset_type === 'backdrop' && a.media_rights_status !== 'blocked' && a.media_rights_status !== 'unknown' && a.url
            );
            if (backdropAsset?.url || posterAsset?.url) {
              setImageSrc(backdropAsset?.url || posterAsset?.url || data.backdrop_url || data.poster_url || PLACEHOLDER_IMAGE);
            }
          }
        } catch {
          // Non-blocking — assets endpoint is optional
        }

        if (user) {
          try {
            const progress = await getWatchProgress(data.id);
            const pos = progress.current_time_seconds;
            if (pos >= MIN_RESUME_SECONDS && !progress.is_completed) {
              setSavedPosition(pos);
              setShowResumePrompt(true);
            }
          } catch {
            // Non-blocking
          }
        } else {
          // Guest: check localStorage for a saved resume position
          const guestProgress = getGuestWatchProgressForMovie(data.id);
          if (guestProgress && guestProgress.current_time_seconds >= MIN_RESUME_SECONDS && guestProgress.progress_percent < 95) {
            setSavedPosition(guestProgress.current_time_seconds);
            setShowResumePrompt(true);
          }
        }

        // NOTE: Do NOT call recordWatch(data.id, 0) here.
        // The old call reset playback_position_seconds to 0 in the database,
        // destroying the saved resume position that was just fetched above.
        // The watch_progress save during actual playback already creates/updates
        // the history record via the upsert in save_watch_progress.
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
        <div className="resume-prompt">
          <span>Continue from <strong>{formatTime(savedPosition)}</strong>?</span>
          <button onClick={handleResume} className="resume-prompt__btn-primary">
            Resume
          </button>
          <button onClick={handleRestart} className="resume-prompt__btn-secondary">
            Start over
          </button>
        </div>
      )}

      {movie.video_status === 'ready' && movie.hls_playlist_url ? (
        <div
          className={`movie-player-container ${
            movie.backdrop_url
              ? 'movie-player-container--backdrop'
              : 'movie-player-container--portrait-poster'
          }`}
        >
          <HlsPlayer
            src={resolveMediaUrl(movie.hls_playlist_url) || movie.hls_playlist_url}
            poster={imageSrc}
            initialTime={initialTime}
            onTimeUpdate={handleTimeUpdate}
            onPause={handlePause}
            onEnded={handleEnded}
          />
        </div>
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
            <div className="video-status-banner video-status-banner--processing">
              <strong>Processing:</strong> High-Definition video is currently being generated. Check back shortly!
            </div>
          )}
          {movie.video_status === 'failed' && (
            <div className="video-status-banner video-status-banner--failed">
              <strong>Error:</strong>{' '}
              {movie.processing_error ?? 'Video stream conversion failed. Please contact an administrator.'}
            </div>
          )}
        </>
      )}

      <h1>{movie.title}</h1>
      <p>{movie.overview}</p>

      {/* ── Metadata block ────────────────────────────────────────────── */}
      <div className="movie-meta-block">

        {/* Release year + Director — plain text rows */}
        <p className="movie-meta-row">
          <span className="movie-meta-label">Release Year</span>
          <span>{movie.release_date ? movie.release_date.split('-')[0] : 'N/A'}</span>
        </p>
        <p className="movie-meta-row">
          <span className="movie-meta-label">Director</span>
          <span>{movie.director || 'N/A'}</span>
        </p>

        {/* Cast — one scrollable row of actor badges (hidden when empty) */}
        {movie.cast && movie.cast.length > 0 && (
          <div className="movie-meta-row movie-meta-scroll-row">
            <span className="movie-meta-label">Cast</span>
            <div className="movie-meta-scroll-track">
              {movie.cast.map((actor) => (
                <span key={actor} className="detail-cast-badge">
                  {actor}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Keywords — one scrollable row of hashtag badges (hidden when empty) */}
        {movie.keywords && movie.keywords.length > 0 && (
          <div className="movie-meta-row movie-meta-scroll-row">
            <span className="movie-meta-label">Keywords</span>
            <div className="movie-meta-scroll-track">
              {movie.keywords.map((kw) => (
                <span key={kw} className="detail-keyword-badge">
                  #{kw}
                </span>
              ))}
            </div>
          </div>
        )}

      </div>

      {/* ── Source & License ───────────────────────────────────────────── */}
      <SourceAttribution movie={movie} />

      {/* Per-asset attribution (only shown for assets with source data) */}
      {assets.filter(a => a.source_name || a.attribution || a.license_type).map(a => (
        <SourceAttribution key={a.id} asset={a} label={`${a.asset_type} — Source`} />
      ))}

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
          <h2>Recommended for You</h2>
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
