import React from 'react';
import type { Movie } from '../../models';

interface MovieTableProps {
  movies: Movie[];
  onEdit: (movie: Movie) => void;
  onDelete: (movie: Movie) => void;
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

/** Colour-coded badge + optional indeterminate bar for the video pipeline status. */
const VideoStatusCell: React.FC<{ movie: Movie }> = ({ movie }) => {
  const status = movie.video_status ?? 'no_video';

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
            ▶
          </a>
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

      {/* One-line error hint */}
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

const MovieTable: React.FC<MovieTableProps> = ({ movies, onEdit, onDelete }) => {
  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Director</th>
            <th>Release Year</th>
            <th>Quality</th>
            <th>Video Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {movies.map((movie) => (
            <tr key={movie.id}>
              <td>{movie.title}</td>
              <td>{movie.director || '—'}</td>
              <td>{movie.release_date ? movie.release_date.split('-')[0] : '—'}</td>
              <td><QualityCell movie={movie} /></td>
              <td><VideoStatusCell movie={movie} /></td>
              <td className="admin-table-actions">
                <button
                  className="btn btn--edit"
                  onClick={() => onEdit(movie)}
                >
                  Edit
                </button>
                <button
                  className="btn btn--delete"
                  onClick={() => onDelete(movie)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MovieTable;
