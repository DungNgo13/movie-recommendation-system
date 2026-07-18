import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getLocalizedTitle, getLocalizedOverview, getLocalizedKeywordLabel } from '../utils/localizedMovie';
import type { AppLanguage } from '../i18n/languageStorage';
import type { Movie, MovieAsset, MovieListItem } from '../models';
import { getMovieById, getMoviesByMetadata } from '../services/movieService';
import type { MetadataFilterType } from '../services/movieService';
import { API_BASE_URL, resolveMediaUrl } from '../config';
import {
  saveWatchProgress,
  saveWatchProgressBeacon,
  getWatchProgress,
  saveGuestWatchProgress,
  getGuestWatchProgressForMovie,
  isWatchCompleted,
  formatPlaybackTime,
} from '../services/continueWatchingService';
import { getMyRating, rateMovie } from '../services/ratingService';
import { getRecommendations } from '../services/recommendationService';
import type { RecommendedMovie } from '../services/recommendationService';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuthHook';
import RecommendationCard from '../components/RecommendationCard';
import MovieCard from '../components/MovieCard';
import StarRating from '../components/StarRating';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import HlsPlayer from '../components/HlsPlayer';
import SourceAttribution from '../components/SourceAttribution';

interface ActiveMetadataFilter {
  type: MetadataFilterType;
  value: string;
}

const PLACEHOLDER_IMAGE = '/placeholder-poster.svg';
// Save position every N seconds of playback change
const SAVE_INTERVAL_SECONDS = 15;
// Only prompt to resume if position is at least this many seconds in.
// Lowered to 3 so short videos (e.g. 31s) can show a resume prompt.
const MIN_RESUME_SECONDS = 3;

const MovieDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t, i18n } = useTranslation(['movies', 'recommendation']);
  const [movie, setMovie] = useState<Movie | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string>(PLACEHOLDER_IMAGE);
  const [myRating, setMyRating] = useState<number | null>(null);
  const [personalizedRecs, setPersonalizedRecs] = useState<RecommendedMovie[]>([]);
  const [assets, setAssets] = useState<MovieAsset[]>([]);

  // ── Metadata discovery mode ──────────────────────────────────────
  const [activeMetadataFilter, setActiveMetadataFilter] = useState<ActiveMetadataFilter | null>(null);
  const [metadataMovies, setMetadataMovies] = useState<MovieListItem[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const metadataAbortRef = useRef<AbortController | null>(null);

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
    if (!Number.isFinite(currentTime) || !Number.isFinite(duration) || duration <= 0) {
      if (import.meta.env.DEV) {
        console.debug('[watch-progress] save skipped — invalid values', {
          currentTime, duration, reason: 'non-finite or duration<=0',
        });
      }
      return;
    }
    lastDurationRef.current = duration;
    if (!movie) return;
    if (Math.abs(currentTime - lastSavedTimeRef.current) >= SAVE_INTERVAL_SECONDS) {
      lastSavedTimeRef.current = currentTime;
      if (import.meta.env.DEV) {
        console.debug('[watch-progress] save accepted', {
          movieId: movie.id, currentTime, duration, trigger: 'timeupdate',
        });
      }
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
    if (import.meta.env.DEV) {
      console.debug('[watch-progress] save accepted', {
        movieId: movie.id, currentTime, duration, trigger: 'pause',
      });
    }
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

  /**
   * Shared helper — saves current progress from refs.
   * @param beacon  Use keepalive/beacon transport (for page-exit events).
   */
  const saveProgressFromRefs = (beacon = false) => {
    const pos = lastSavedTimeRef.current;
    const dur = lastDurationRef.current;
    if (movieRef.current && Number.isFinite(pos) && Number.isFinite(dur) && pos > 1 && dur > 0) {
      if (import.meta.env.DEV) {
        console.debug('[watch-progress] save accepted', {
          movieId: movieRef.current.id, currentTime: pos, duration: dur,
          trigger: beacon ? 'page-exit (beacon)' : 'unmount',
        });
      }
      if (userRef.current) {
        if (beacon) {
          // Use keepalive fetch — survives page unload
          saveWatchProgressBeacon(movieRef.current.id, pos, dur);
        } else {
          saveWatchProgress(movieRef.current.id, pos, dur);
        }
      } else {
        saveGuestWatchProgress(movieRef.current.id, pos, dur);
      }
    }
  };

  // Save on: unmount, visibilitychange (tab hidden), beforeunload (page close)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // Use beacon transport — page may be closing
        saveProgressFromRefs(true);
      }
    };
    const handleBeforeUnload = () => {
      // Use beacon transport — regular fetch gets cancelled during unload
      saveProgressFromRefs(true);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Final save on component unmount (route change) — regular fetch is fine here
      saveProgressFromRefs();
    };
  }, []);

  // Fetch personalized recommendations (only for authenticated users)
  useEffect(() => {
    if (!user) { setPersonalizedRecs([]); return; }
    getRecommendations(4).then(setPersonalizedRecs).catch(() => {});
  }, [user]);

  // Reset metadata mode when navigating to a different movie
  useEffect(() => {
    setActiveMetadataFilter(null);
    setMetadataMovies([]);
    setMetadataError(null);
    setMetadataLoading(false);
    metadataAbortRef.current?.abort();
  }, [id]);

  // Fetch metadata movies when filter changes
  useEffect(() => {
    if (!activeMetadataFilter || !movie) return;

    // Cancel previous metadata request
    metadataAbortRef.current?.abort();
    const controller = new AbortController();
    metadataAbortRef.current = controller;

    setMetadataLoading(true);
    setMetadataError(null);

    getMoviesByMetadata(
      { type: activeMetadataFilter.type, value: activeMetadataFilter.value },
      { excludeMovieId: movie.id, limit: 10, signal: controller.signal },
    )
      .then((items) => {
        if (!controller.signal.aborted) {
          setMetadataMovies(items);
          setMetadataLoading(false);
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return; // don't treat abort as error
        setMetadataError(err?.message || 'Failed to load metadata movies');
        setMetadataLoading(false);
      });

    return () => controller.abort();
  }, [activeMetadataFilter, movie]);

  // ── Metadata filter handler ──────────────────────────────────────
  const handleMetadataFilter = useCallback((type: MetadataFilterType, value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setActiveMetadataFilter({ type, value: trimmed });
  }, []);

  const clearMetadataFilter = useCallback(() => {
    metadataAbortRef.current?.abort();
    setActiveMetadataFilter(null);
    setMetadataMovies([]);
    setMetadataError(null);
    setMetadataLoading(false);
  }, []);

  const isMetadataMode = activeMetadataFilter !== null;

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
            if (import.meta.env.DEV) {
              console.debug('[watch-progress] resume check', {
                movieId: data.id, savedPosition: pos,
                isCompleted: progress.is_completed,
                meetsMinimum: pos >= MIN_RESUME_SECONDS,
              });
            }
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
          if (
            guestProgress &&
            guestProgress.playback_position_seconds >= MIN_RESUME_SECONDS &&
            !isWatchCompleted(guestProgress.progress_percent)
          ) {
            setSavedPosition(guestProgress.playback_position_seconds);
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
          <span>Continue from <strong>{formatPlaybackTime(savedPosition)}</strong>?</span>
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

      <h1>{getLocalizedTitle(movie, i18n.language as AppLanguage)}</h1>
      <p>{getLocalizedOverview(movie, i18n.language as AppLanguage)}</p>

      {/* ── Metadata block ────────────────────────────────────────────── */}
      <div className="movie-meta-block">

        {/* Release year — plain text */}
        <p className="movie-meta-row">
          <span className="movie-meta-label">Release Year</span>
          <span>{movie.release_date ? movie.release_date.split('-')[0] : 'N/A'}</span>
        </p>

        {/* Director — clickable button */}
        <p className="movie-meta-row">
          <span className="movie-meta-label">{t("movies:detail.director", "Director")}</span>
          {movie.director ? (
            <button
              type="button"
              className="movie-metadata-button"
              onClick={() => handleMetadataFilter('director', movie.director!)}
              aria-label={`Show movies directed by ${movie.director}`}
            >
              {movie.director}
            </button>
          ) : (
            <span>N/A</span>
          )}
        </p>

        {/* Cast — clickable chips */}
        {movie.cast && movie.cast.length > 0 && (
          <div className="movie-meta-row movie-meta-scroll-row">
            <span className="movie-meta-label">{t("movies:detail.cast", "Cast")}</span>
            <div className="movie-meta-scroll-track">
              {movie.cast.map((actor) => (
                <button
                  key={actor}
                  type="button"
                  className="movie-metadata-chip detail-cast-badge"
                  onClick={() => handleMetadataFilter('cast', actor)}
                  aria-label={`Show movies featuring ${actor}`}
                >
                  {actor}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Keywords — clickable chips */}
        {movie.keywords && movie.keywords.length > 0 && (
          <div className="movie-meta-row movie-meta-scroll-row">
            <span className="movie-meta-label">{t("movies:detail.keywords", "Keywords")}</span>
            <div className="movie-meta-scroll-track">
              {movie.keywords.map((kw) => {
                const localizedKw = getLocalizedKeywordLabel(kw, movie.keyword_labels_vi, i18n.language as AppLanguage);
                return (
                  <button
                    key={kw}
                    type="button"
                    className="movie-metadata-chip detail-keyword-badge"
                    onClick={() => handleMetadataFilter('keyword', kw)}
                    aria-label={`Show movies tagged ${localizedKw}`}
                  >
                    #{localizedKw}
                  </button>
                );
              })}
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

      {/* ── Recommendation / Metadata Discovery Section ────────────── */}
      {(personalizedRecs.length > 0 || isMetadataMode) && (
        <section className="recommendations-section">

          {/* Section header with filter controls */}
          {isMetadataMode ? (
            <div className="recommendation-mode-header">
              <h2>
                {activeMetadataFilter.type === 'director' && t("movies:metadata.moreByDirector", "More by {{director}}", { director: activeMetadataFilter.value })}
                {activeMetadataFilter.type === 'cast' && t("movies:metadata.featuringCast", "Movies featuring {{cast}}", { cast: activeMetadataFilter.value })}
                {activeMetadataFilter.type === 'keyword' && t("movies:metadata.taggedKeyword", "Movies tagged #{{keyword}}", { keyword: getLocalizedKeywordLabel(activeMetadataFilter.value, movie.keyword_labels_vi, i18n.language as AppLanguage) })}
              </h2>
              <div className="recommendation-filter-controls">
                <span className="recommendation-filter-chip">
                  {activeMetadataFilter.type === 'keyword' ? `#${getLocalizedKeywordLabel(activeMetadataFilter.value, movie.keyword_labels_vi, i18n.language as AppLanguage)}` : activeMetadataFilter.value}
                  <button
                    type="button"
                    className="recommendation-filter-chip__dismiss"
                    onClick={clearMetadataFilter}
                    aria-label="Remove filter"
                  >
                    ×
                  </button>
                </span>
                <button
                  type="button"
                  className="recommendation-filter-clear"
                  onClick={clearMetadataFilter}
                >
                  {t("movies:metadata.backToRecommendations", "Back to Recommendations")}
                </button>
              </div>
            </div>
          ) : (
            <h2>{t("recommendation:title", "Recommended for You")}</h2>
          )}

          {/* Metadata mode content */}
          {isMetadataMode && (
            <>
              {metadataLoading && <LoadingSpinner />}
              {metadataError && (
                <div className="metadata-error-state">
                  <p>Unable to load movies for {activeMetadataFilter.type === 'keyword' ? `#${activeMetadataFilter.value}` : activeMetadataFilter.value}.</p>
                  <button type="button" className="btn btn--secondary" onClick={clearMetadataFilter}>
                    Back to personalized recommendations
                  </button>
                </div>
              )}
              {!metadataLoading && !metadataError && metadataMovies.length === 0 && (
                <div className="metadata-empty-state">
                  <p>{t("movies:metadata.noOtherMovies", "No other movies found.")}</p>
                  <button type="button" className="btn btn--secondary" onClick={clearMetadataFilter}>
                    {t("movies:metadata.backToRecommendations", "Back to Recommendations")}
                  </button>
                </div>
              )}
              {!metadataLoading && !metadataError && metadataMovies.length > 0 && (
                <div className="movie-list">
                  {metadataMovies.map((m) => (
                    <div key={m.id} className="metadata-result-card">
                      <MovieCard
                        movie={m}
                        isFavorite={isFavorite(m.id)}
                        onToggleFavorite={toggleFavorite}
                      />
                      <span className="metadata-match-label">
                        {activeMetadataFilter.type === 'director' && `Director: ${activeMetadataFilter.value}`}
                        {activeMetadataFilter.type === 'cast' && `Cast match: ${activeMetadataFilter.value}`}
                        {activeMetadataFilter.type === 'keyword' && `Keyword match: #${activeMetadataFilter.value}`}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Personalized mode content */}
          {!isMetadataMode && (
            <div className="movie-list">
              {personalizedRecs.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  movie={rec}
                  isFavorite={isFavorite(rec.id)}
                  onToggleFavorite={toggleFavorite}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default MovieDetailPage;
