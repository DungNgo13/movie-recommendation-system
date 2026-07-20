import React, { useState } from 'react';
import type { Movie } from '../../models';
import { useTranslation } from 'react-i18next';

interface MovieTableProps {
  movies: Movie[];
  onEdit: (movie: Movie) => void;
  onDelete: (movie: Movie) => void;
  onCancelEncode: (movie: Movie) => Promise<void>;
  onStartEncode: (movie: Movie) => Promise<void>;
}

/** Green pill for a single resolved quality label like "720p". */
const QualityBadge: React.FC<{ label: string }> = ({ label }) => (
  <span style={{
    display: 'inline-block',
    padding: '2px 7px',
    marginRight: '3px',
    borderRadius: '8px',
    fontSize: '0.7rem',
    fontWeight: 700,
    background: '#d4edda',
    color: '#155724',
  }}>
    {label}
  </span>
);

/**
 * Quality column cell — three visible states:
 *  1. "Processing..."  → yellow badge + spinner (set by router on encode start)
 *  2. "360p,720p,…"   → green resolution pills  (set by service on encode finish)
 *  3. null / missing  → grey "Pending" badge
 */
const QualityCell: React.FC<{ movie: Movie }> = ({ movie }) => {
  const q = movie.available_qualities;

  // ── State 1: actively encoding ────────────────────────────────────────────
  if (q === 'Processing...') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: '5px',
        padding: '2px 8px', borderRadius: '8px',
        fontSize: '0.7rem', fontWeight: 600,
        background: '#fff3cd', color: '#856404',
      }}>
        {/* Inline CSS spinner — no extra library needed */}
        <span style={{
          display: 'inline-block',
          width: '8px', height: '8px',
          border: '2px solid #856404',
          borderTopColor: 'transparent',
          borderRadius: '50%',
          animation: 'spin 0.7s linear infinite',
          flexShrink: 0,
        }} />
        Encoding…
      </span>
    );
  }

  // ── State 2: resolutions known ────────────────────────────────────────────
  if (q) {
    return (
      <div style={{ whiteSpace: 'nowrap' }}>
        {q.split(',').map((label) => (
          <QualityBadge key={label} label={label.trim()} />
        ))}
      </div>
    );
  }

  // ── State 3: not yet encoded ──────────────────────────────────────────────
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: '8px',
      fontSize: '0.7rem', fontWeight: 600,
      background: '#e9ecef', color: '#6c757d',
    }}>
      Pending
    </span>
  );
};

// ─── Data Quality Cell ───────────────────────────────────────────────────────
// Mirrors the backend compute_quality_score() formula so the tooltip is
// always consistent with the number coming from the API.

/** Returns a human-readable list of which AI fields are still empty. */
function getMissingFields(movie: Movie): string[] {
  const missing: string[] = [];
  if (!movie.genres?.length)                           missing.push('Genres (+30)');
  if (!movie.cast?.length)                             missing.push('Cast (+20)');
  if (!movie.overview || movie.overview.length <= 50)  missing.push('Overview >50 chars (+20)');
  if (!movie.director)                                 missing.push('Director (+15)');
  if (!movie.poster_url || !movie.backdrop_url)        missing.push('Poster & Backdrop (+10)');
  return missing;
}

/** Colour thresholds matching the brief */
function scoreColor(score: number): string {
  if (score >= 80) return '#27ae60'; // green  — optimised
  if (score >= 50) return '#f39c12'; // amber  — average
  return '#e74c3c';                  // red    — critical
}

/**
 * SVG ring gauge (donut chart) showing quality_score 0–100.
 * The ring fill is the only moving part; no external library needed.
 */
const DataQualityCell: React.FC<{ movie: Movie }> = ({ movie }) => {
  const score  = movie.quality_score ?? 0;
  const color  = scoreColor(score);
  const missing = getMissingFields(movie);

  // SVG ring maths
  const R   = 16;                           // radius of the ring
  const C   = 2 * Math.PI * R;             // full circumference
  const arc = C * (score / 100);           // filled arc length

  // Tooltip — shows missing fields or a success message
  const tooltip = missing.length === 0
    ? 'All AI fields complete — engine fully optimised'
    : `Missing:\n${missing.map(f => `  - ${f}`).join('\n')}`;

  // Label under the ring — severity text
  const label =
    score >= 80 ? 'Optimised' :
    score >= 50 ? 'Average'   : 'Critical';

  return (
    <div
      title={tooltip}
      style={{
        display:        'inline-flex',
        flexDirection:  'column',
        alignItems:     'center',
        gap:            3,
        cursor:         'help',
        userSelect:     'none',
      }}
    >
      {/* SVG donut ring */}
      <svg width={40} height={40} viewBox="0 0 40 40">
        {/* Track ring (grey background) */}
        <circle
          cx={20} cy={20} r={R}
          fill="none"
          stroke="#e9ecef"
          strokeWidth={5}
        />
        {/* Score arc — rotated so it starts at 12 o'clock */}
        <circle
          cx={20} cy={20} r={R}
          fill="none"
          stroke={color}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={`${arc} ${C - arc}`}
          strokeDashoffset={C / 4}   /* rotate to 12 o'clock */
          style={{ transition: 'stroke-dasharray 0.4s ease' }}
        />
        {/* Score number in the centre */}
        <text
          x={20} y={20}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={9}
          fontWeight={700}
          fill={color}
        >
          {score}
        </text>
      </svg>

      {/* Severity label */}
      <span style={{
        fontSize:   '0.65rem',
        fontWeight: 600,
        color,
        letterSpacing: '0.02em',
      }}>
        {label}
      </span>
    </div>
  );
};

/** Colour-coded badge + optional indeterminate bar for the video pipeline status. */
const VideoStatusCell: React.FC<{
  movie: Movie;
  onCancelEncode: (movie: Movie) => Promise<void>;
  onStartEncode:  (movie: Movie) => Promise<void>;
}> = ({ movie, onCancelEncode, onStartEncode }) => {
  const status = movie.video_status ?? 'no_video';
  const [isCancelling, setIsCancelling] = useState(false);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await onCancelEncode(movie);
    } finally {
      setIsCancelling(false);
    }
  };

  const badgeStyle: React.CSSProperties = {
    display: 'inline-block',
    padding: '2px 9px',
    borderRadius: '10px',
    fontSize: '0.72rem',
    fontWeight: 700,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    ...(status === 'ready'
      ? { background: '#d4edda', color: '#155724' }
      : status === 'processing'
      ? { background: '#fff3cd', color: '#856404' }
      : status === 'failed'
      ? { background: '#f8d7da', color: '#721c24' }
      : status === 'uploaded'
      ? { background: '#d1ecf1', color: '#0c5460' }
      : status === 'no_video'
      ? { background: '#e2e3e5', color: '#383d41' }
      : { background: '#e9ecef', color: '#6c757d' }),
  };

  return (
    <div style={{ minWidth: '130px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: status === 'processing' ? '5px' : 0 }}>
        <span style={badgeStyle}>{status}</span>
        {status === 'ready' && movie.hls_playlist_url && (
          <a
            href={movie.hls_playlist_url}
            target="_blank"
            rel="noopener noreferrer"
            title="HLS playlist"
            style={{ fontSize: '0.85rem', color: '#155724', lineHeight: 1 }}
          >
            Play
          </a>
        )}
        {/* ── Cancel encode button — visible only while encoding ── */}
        {status === 'processing' && (
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            title="Stop encoding"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: '8px',
              border: 'none',
              cursor: isCancelling ? 'not-allowed' : 'pointer',
              fontSize: '0.7rem',
              fontWeight: 700,
              background: isCancelling ? '#e9ecef' : '#f8d7da',
              color: isCancelling ? '#6c757d' : '#721c24',
              transition: 'background 0.2s',
              flexShrink: 0,
            }}
          >
            ⬛ {isCancelling ? 'Cancelling…' : 'Stop'}
          </button>
        )}
      </div>

      {/* Dynamic progress animated bar */}
      {status === 'processing' && (
        <div style={{ marginTop: '4px' }}>
          <div style={{ fontSize: '0.75rem', color: '#856404', marginBottom: '4px' }}>
            {movie.video_step || 'Processing'} — {movie.video_progress ?? 0}%
          </div>
          <div className="vst-track">
             <div 
               style={{
                 height: '100%',
                 background: 'linear-gradient(90deg, #ffc107, #fd7e14)',
                 width: `${movie.video_progress ?? 0}%`,
                 transition: 'width 0.5s ease-out',
                 borderRadius: '3px'
               }} 
             />
          </div>
        </div>
      )}

      {/* ── One-click encode trigger — visible for uploaded / failed / ready ── */}
      {(status === 'uploaded' || status === 'failed' || status === 'ready') && (
        <button
          onClick={() => onStartEncode(movie)}
          title={status === 'ready' ? 'Re-encode (replace existing HLS)' : 'Start multi-quality HLS encoding'}
          style={{
            marginTop: '6px',
            display: 'inline-flex', alignItems: 'center', gap: '4px',
            padding: '2px 10px', borderRadius: '8px', border: 'none',
            cursor: 'pointer', fontSize: '0.7rem', fontWeight: 700,
            background: status === 'ready' ? '#d1ecf1' : '#d4edda',
            color:      status === 'ready' ? '#0c5460'  : '#155724',
            transition: 'background 0.2s',
          }}
        >
          {status === 'ready' ? 'Re-encode' : 'Encode'}
        </button>
      )}

      {/* One-line error hint — only when encoding failed */}
      {status === 'failed' && movie.processing_error && (
        <div
          title={movie.processing_error}
          style={{
            marginTop: '3px',
            fontSize: '0.72rem',
            color: '#721c24',
            maxWidth: '200px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {movie.processing_error}
        </div>
      )}
    </div>
  );
};

const MovieTable: React.FC<MovieTableProps> = ({ movies, onEdit, onDelete, onCancelEncode, onStartEncode }) => {
  const { t } = useTranslation(['admin', 'common']);

  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>{t("admin:movieForm.fields.title", "Title (English)")}</th>
            <th>{t("admin:movieForm.fields.director", "Director")}</th>
            <th>{t("admin:movieForm.fields.releaseDate", "Release Year")}</th>
            <th>Quality</th>
            <th
              title="Data completeness score for the AI recommendation engine (0–100). Hover each row for missing fields."
              style={{ cursor: 'help', whiteSpace: 'nowrap' }}
            >
              Data Quality
            </th>
            <th>Video Status</th>
            <th>{t("admin:tables.actions", "Actions")}</th>
          </tr>
        </thead>
        <tbody>
          {movies.map((movie) => (
            <tr key={movie.id}>
              <td>
                <div style={{ fontWeight: 500 }}>{movie.title}</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #6c757d)' }}>
                  {movie.title_vi || <span style={{ fontStyle: 'italic', opacity: 0.7 }}>{t("admin:tables.noTitleVi", "No Vietnamese title")}</span>}
                </div>
              </td>
              <td>{movie.director || '—'}</td>
              <td>{movie.release_date ? movie.release_date.split('-')[0] : '—'}</td>
              <td><QualityCell movie={movie} /></td>
              <td style={{ textAlign: 'center' }}>
                <DataQualityCell movie={movie} />
              </td>
              <td><VideoStatusCell movie={movie} onCancelEncode={onCancelEncode} onStartEncode={onStartEncode} /></td>
              <td className="admin-table-actions">
                <div className="admin-table-actions__inner">
                  <button
                    type="button"
                    className="btn btn--edit"
                    onClick={() => onEdit(movie)}
                  >
                    {t("admin:tables.edit", "Edit")}
                  </button>
                  <button
                    type="button"
                    className="btn btn--delete"
                    onClick={() => onDelete(movie)}
                  >
                    {t("admin:tables.delete", "Delete")}
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MovieTable;
