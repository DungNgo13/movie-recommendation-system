import React from 'react';
import { Link } from 'react-router-dom';
import HeartIcon from './HeartIcon';
import { formatPlaybackTime } from '../services/continueWatchingService';
import { useTranslation } from 'react-i18next';
import { getLocalizedTitle } from '../utils/localizedMovie';

interface ContinueWatchingCardProps {
  movie: {
    id: string;
    title: string;
    title_vi?: string | null;
    poster_url: string | null;
  };
  progressPercent: number;
  playbackPositionSeconds: number;
  isFavorite: boolean;
  onToggleFavorite: (id: string) => void | Promise<void>;
  favoriteLoading?: boolean;
}

/** Inline SVG play icon — decorative. */
const PlayIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
  >
    <path d="M8 5v14l11-7z" />
  </svg>
);

const ContinueWatchingCard: React.FC<ContinueWatchingCardProps> = ({
  movie,
  progressPercent,
  playbackPositionSeconds,
  isFavorite,
  onToggleFavorite,
  favoriteLoading = false,
}) => {
  const { t, i18n } = useTranslation(['movies']);
  const localizedTitle = getLocalizedTitle(movie as any, i18n.language as any);
  // ── Progress data safety ──────────────────────────────────────────
  const clampedProgress = Math.min(
    100,
    Math.max(0, Number.isFinite(progressPercent) ? progressPercent : 0),
  );
  const roundedProgress = Math.round(clampedProgress);
  const formattedPosition = formatPlaybackTime(playbackPositionSeconds);

  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (favoriteLoading) return;
    onToggleFavorite(movie.id);
  };

  const favoriteLabel = isFavorite
    ? `Remove ${localizedTitle} from favorites`
    : `Add ${localizedTitle} to favorites`;

  return (
    <article className="cw-card">
      <Link to={`/movie/${movie.id}`} className="cw-card__link">
        {/* ── Media area ── */}
        <div className="cw-card__media">
          <img
            src={movie.poster_url || '/placeholder-poster.svg'}
            alt={`${localizedTitle} poster`}
            className="cw-card__poster"
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = '/placeholder-poster.svg';
            }}
          />
          {/* Favorite heart */}
          <button
            type="button"
            className={`movie-card__favorite-button${isFavorite ? ' movie-card__favorite-button--active' : ''}`}
            onClick={handleFavoriteClick}
            disabled={favoriteLoading}
            aria-label={favoriteLabel}
            title={favoriteLabel}
          >
            <HeartIcon filled={isFavorite} className="movie-card__favorite-icon" />
          </button>
        </div>

        {/* ── Content footer ── */}
        <div className="cw-card__content">
          <h3 className="cw-card-title">{localizedTitle}</h3>
          <p className="cw-card-progress">
            {t("movies:continueWatching.progress", "▶ {{time}} · {{percent}}%", {
              time: formatPlaybackTime(playbackPositionSeconds),
              percent: progressPercent > 0 && progressPercent < 1 ? '<1' : Math.floor(progressPercent)
            })}
          </p>

          {/* Accessible progress bar */}
          <div
            className="cw-card__progress"
            role="progressbar"
            aria-label={`Watched ${roundedProgress}% of ${localizedTitle}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={roundedProgress}
          >
            <div
              className="cw-card__progress-fill"
              style={{ width: `${clampedProgress}%` }}
            />
          </div>

          {/* Resume time + percentage */}
          <div className="cw-resume-indicator">
            <span className="cw-resume-text">{t("movies:continueWatching.resume", "Resume")}</span>
            <PlayIcon className="cw-resume-icon" />
          </div>
        </div>
      </Link>
    </article>
  );
};

export default ContinueWatchingCard;
