import React from 'react';
import type { Movie } from '../../models';

interface MovieTableProps {
  movies: Movie[];
  onEdit: (movie: Movie) => void;
  onDelete: (movie: Movie) => void;
}

/** Colour-coded badge + optional indeterminate bar for the video pipeline status. */
const VideoStatusCell: React.FC<{ movie: Movie }> = ({ movie }) => {
  const status = movie.video_status ?? 'pending';

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

      {/* Indeterminate animated bar — only while processing */}
      {status === 'processing' && (
        <div className="vst-track">
          <div className="vst-bar" />
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
