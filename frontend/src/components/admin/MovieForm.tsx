import React, { useState, useEffect } from 'react';
import type { Movie } from '../../models';
import type { MovieFormData } from '../../services/movieService';
import { uploadMovieImage, uploadMovieVideo, processMovieVideo, getMovieProcessingStatus } from '../../services/movieService';

interface MovieFormProps {
  movie: Movie | null;
  onSubmit: (data: MovieFormData) => void;
  onCancel: () => void;
}

const MovieForm: React.FC<MovieFormProps> = ({ movie, onSubmit, onCancel }) => {
  const [title, setTitle] = useState('');
  const [overview, setOverview] = useState('');
  const [releaseDate, setReleaseDate] = useState('');
  const [director, setDirector] = useState('');
  const [posterUrl, setPosterUrl] = useState('');
  const [backdropUrl, setBackdropUrl] = useState('');
  const [videoStatus, setVideoStatus] = useState('pending');
  const [videoUrl, setVideoUrl] = useState('');
  const [hlsUrl, setHlsUrl] = useState('');
  const [availableQualities, setAvailableQualities] = useState<string | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [pollProgress, setPollProgress] = useState<number>(0);
  const [pollStep, setPollStep] = useState<string>('Processing');

  useEffect(() => {
    if (movie) {
      setTitle(movie.title);
      setOverview(movie.overview || '');
      setReleaseDate(movie.release_date ? movie.release_date.split('-')[0] : '');
      setDirector(movie.director || '');
      setPosterUrl(movie.poster_url || '');
      setBackdropUrl(movie.backdrop_url || '');
      setVideoUrl(movie.video_url || '');
      setVideoStatus(movie.video_status || 'pending');
      setHlsUrl(movie.hls_playlist_url || '');
      setAvailableQualities(movie.available_qualities || null);
      setProcessingError(movie.processing_error || null);
    }
  }, [movie]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: 'poster' | 'backdrop') => {
    if (!movie || !e.target.files?.[0]) return;
    try {
      setUploading(true);
      setError(null);
      const updatedMovie = await uploadMovieImage(movie.id, e.target.files[0], type);
      if (type === 'poster') setPosterUrl(updatedMovie.poster_url || '');
      if (type === 'backdrop') setBackdropUrl(updatedMovie.backdrop_url || '');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(msg);
    } finally {
      setUploading(false);
      e.target.value = ''; // Reset file input
    }
  };

  useEffect(() => {
    let interval: number;
    if (movie && videoStatus === 'processing') {
      interval = window.setInterval(async () => {
        try {
          const res = await getMovieProcessingStatus(movie.id);
          setVideoStatus(res.video_status);
          setPollProgress(res.video_progress ?? 0);
          setPollStep(res.video_step || 'Processing');
          if (res.hls_playlist_url) setHlsUrl(res.hls_playlist_url);
          if (res.processing_error) setProcessingError(res.processing_error);
          if ((res as { available_qualities?: string }).available_qualities) {
            setAvailableQualities((res as { available_qualities?: string }).available_qualities ?? null);
          }
        } catch (e) {
          console.warn('Polling error', e);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [movie, videoStatus]);

  const handleProcessHls = async () => {
    if (!movie) return;
    try {
      setUploading(true);
      setError(null);
      await processMovieVideo(movie.id);
      setVideoStatus('processing');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Processing failed';
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!movie || !e.target.files?.[0]) return;
    try {
      setUploading(true);
      setError(null);
      setUploadPercent(0);
      const updatedMovie = await uploadMovieVideo(movie.id, e.target.files[0], (pct) => {
        setUploadPercent(pct);
      });
      setVideoUrl(updatedMovie.video_url || '');
      setVideoStatus(updatedMovie.video_status || 'uploaded');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Video upload failed';
      setError(msg);
    } finally {
      setUploading(false);
      setUploadPercent(null);
      e.target.value = '';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Title is required.');
      return;
    }

    onSubmit({
      title: title.trim(),
      overview: overview.trim() || null,
      release_date: releaseDate ? `${releaseDate.trim()}-01-01` : null,
      director: director.trim() || null,
      poster_url: posterUrl.trim() || null,
      backdrop_url: backdropUrl.trim() || null,
    });
  };

  return (
    <form className="admin-form" onSubmit={handleSubmit}>
      <h2>{movie ? 'Edit Movie' : 'Add Movie'}</h2>

      {error && <p className="admin-form-error">{error}</p>}

      <div className="admin-form-group">
        <label htmlFor="title">Title *</label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Movie title"
        />
      </div>

      <div className="admin-form-group">
        <label htmlFor="overview">Overview</label>
        <textarea
          id="overview"
          value={overview}
          onChange={(e) => setOverview(e.target.value)}
          placeholder="Movie description"
          rows={3}
        />
      </div>

      <div className="admin-form-row">
        <div className="admin-form-group">
          <label htmlFor="release_date">Release Year</label>
          <input
            id="release_date"
            type="number"
            min="1888"
            max="2100"
            value={releaseDate}
            onChange={(e) => setReleaseDate(e.target.value)}
            placeholder="e.g. 2024"
          />
        </div>

        <div className="admin-form-group">
          <label htmlFor="director">Director</label>
          <input
            id="director"
            type="text"
            value={director}
            onChange={(e) => setDirector(e.target.value)}
            placeholder="Director name"
          />
        </div>
      </div>

      <div className="admin-form-group">
        <label htmlFor="poster_url">Poster URL</label>
        <input
          id="poster_url"
          type="text"
          value={posterUrl}
          onChange={(e) => setPosterUrl(e.target.value)}
          placeholder="https://..."
        />
        {movie && (
          <div style={{ marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem' }}>Or Upload File: </label>
            <input 
              type="file" 
              accept="image/jpeg, image/png, image/webp" 
              onChange={(e) => handleUpload(e, 'poster')} 
              disabled={uploading}
            />
          </div>
        )}
      </div>

      <div className="admin-form-group">
        <label htmlFor="backdrop_url">Backdrop URL</label>
        <input
          id="backdrop_url"
          type="text"
          value={backdropUrl}
          onChange={(e) => setBackdropUrl(e.target.value)}
          placeholder="https://..."
        />
        {movie && (
          <div style={{ marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem' }}>Or Upload File: </label>
            <input 
              type="file" 
              accept="image/jpeg, image/png, image/webp" 
              onChange={(e) => handleUpload(e, 'backdrop')} 
              disabled={uploading}
            />
          </div>
        )}
      </div>

      <div className="admin-form-group" style={{ backgroundColor: '#f8f9fa', padding: '1rem', borderRadius: '8px', border: '1px solid #dee2e6', color: '#212529' }}>
        <h3 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1.1rem', color: '#212529' }}>Source Video (.mp4)</h3>
        {movie ? (
          <>
            <div style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
              {/* Status badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <strong>Status:</strong>
                <span style={{
                  display: 'inline-block',
                  padding: '2px 10px',
                  borderRadius: '12px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  backgroundColor:
                    videoStatus === 'ready' ? '#d4edda' :
                    videoStatus === 'processing' ? '#fff3cd' :
                    videoStatus === 'failed' ? '#f8d7da' :
                    videoStatus === 'uploaded' ? '#d1ecf1' :
                    videoStatus === 'no_video' ? '#e2e3e5' : '#e9ecef',
                  color:
                    videoStatus === 'ready' ? '#155724' :
                    videoStatus === 'processing' ? '#856404' :
                    videoStatus === 'failed' ? '#721c24' :
                    videoStatus === 'uploaded' ? '#0c5460' :
                    videoStatus === 'no_video' ? '#383d41' : '#6c757d',
                }}>
                  {videoStatus.toUpperCase()}
                </span>
                {/* Processing spinner */}
                {videoStatus === 'processing' && (
                  <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid #856404', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                )}
              </div>

              {/* Upload progress bar */}
              {uploadPercent !== null && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.8rem', marginBottom: '4px', color: '#495057' }}>
                    Uploading… {uploadPercent}%
                  </div>
                  <div style={{ height: '6px', background: '#dee2e6', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${uploadPercent}%`, background: '#0d6efd', transition: 'width 0.2s ease', borderRadius: '3px' }} />
                  </div>
                </div>
              )}

              {/* Processing Dynamic Status bar */}
              {videoStatus === 'processing' && uploadPercent === null && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.8rem', marginBottom: '4px', color: '#856404' }}>
                    {pollStep} — {pollProgress}%
                  </div>
                  <div style={{ height: '6px', background: '#dee2e6', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${pollProgress}%`,
                      background: 'linear-gradient(90deg, #ffc107, #fd7e14)',
                      borderRadius: '3px',
                      transition: 'width 0.5s ease-out'
                    }} />
                  </div>
                </div>
              )}

              {/* Encoded quality badges */}
              {availableQualities && (
                <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '0.85rem' }}>Qualities:</strong>
                  {availableQualities.split(',').map((q) => (
                    <span key={q} style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: '10px',
                      fontSize: '0.75rem', fontWeight: 700,
                      background: q.trim() === '1080p' ? '#cce5ff' : q.trim() === '720p' ? '#d4edda' : '#e2e3e5',
                      color:      q.trim() === '1080p' ? '#004085' : q.trim() === '720p' ? '#155724' : '#383d41',
                    }}>
                      {q.trim()}
                    </span>
                  ))}
                </div>
              )}

              {videoUrl && (
                <div style={{ wordBreak: 'break-all', marginTop: '4px', opacity: 0.8, fontSize: '0.85rem' }}>
                  <em>Source: {videoUrl}</em>
                </div>
              )}
              {hlsUrl && (
                <div style={{ wordBreak: 'break-all', marginTop: '4px', color: '#155724', fontSize: '0.85rem' }}>
                  <em>HLS: <a href={hlsUrl} target="_blank" rel="noopener noreferrer">{hlsUrl}</a></em>
                </div>
              )}
              {processingError && (
                <div style={{ color: '#721c24', marginTop: '6px', fontSize: '0.85rem', background: '#f8d7da', padding: '8px', borderRadius: '4px' }}>
                  <strong>Error:</strong> {processingError}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="file"
                accept="video/mp4"
                onChange={handleVideoUpload}
                disabled={uploading}
              />

              {/* Show encode button when video is uploaded, failed, or ready (re-encode) */}
              {(videoStatus === 'uploaded' || videoStatus === 'failed' || videoStatus === 'ready') && (
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={handleProcessHls}
                  disabled={uploading}
                  title={videoStatus === 'ready' ? 'Re-encode with current settings' : 'Start multi-quality HLS encoding'}
                >
                  {videoStatus === 'ready' ? '↺ Re-encode' : '▶ Start Multi-Quality Encoding'}
                </button>
              )}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '0.9rem', color: '#6c757d', margin: 0 }}>
            <em>Please create the movie first before uploading the primary video payload.</em>
          </p>
        )}
      </div>

      <div className="admin-form-actions">
        <button type="submit" className="btn btn--primary">
          {movie ? 'Save Changes' : 'Create Movie'}
        </button>
        <button type="button" className="btn btn--secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
};

export default MovieForm;
