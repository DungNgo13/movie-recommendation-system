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
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (movie) {
      setTitle(movie.title);
      setOverview(movie.overview || '');
      setReleaseDate(movie.release_date || '');
      setDirector(movie.director || '');
      setPosterUrl(movie.poster_url || '');
      setBackdropUrl(movie.backdrop_url || '');
      setVideoUrl(movie.video_url || '');
      setVideoStatus(movie.video_status || 'pending');
      setHlsUrl(movie.hls_playlist_url || '');
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
          if (res.hls_playlist_url) setHlsUrl(res.hls_playlist_url);
          if (res.processing_error) setProcessingError(res.processing_error);
        } catch (e) {
          console.warn('Polling error', e);
        }
      }, 5000);
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
      const updatedMovie = await uploadMovieVideo(movie.id, e.target.files[0]);
      setVideoUrl(updatedMovie.video_url || '');
      setVideoStatus(updatedMovie.video_status || 'uploaded');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Video upload failed';
      setError(msg);
    } finally {
      setUploading(false);
      e.target.value = ''; // Reset file input
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
      release_date: releaseDate || null,
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
          <label htmlFor="release_date">Release Date</label>
          <input
            id="release_date"
            type="date"
            value={releaseDate}
            onChange={(e) => setReleaseDate(e.target.value)}
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

      <div className="admin-form-group" style={{ backgroundColor: '#1a1a1a', padding: '1rem', borderRadius: '8px', border: '1px solid #333' }}>
        <h3 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1.1rem' }}>Source Video (.mp4)</h3>
        {movie ? (
          <>
            <div style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
              <strong>Status:</strong> {videoStatus.toUpperCase()}
              {videoUrl && (
                <div style={{ wordBreak: 'break-all', marginTop: '4px', opacity: 0.8 }}>
                  <em>Source: {videoUrl}</em>
                </div>
              )}
              {hlsUrl && (
                <div style={{ wordBreak: 'break-all', marginTop: '4px', color: '#66bb6a' }}>
                  <em>HLS: {hlsUrl}</em>
                </div>
              )}
              {processingError && (
                <div style={{ color: '#ef5350', marginTop: '4px', fontSize: '0.85rem' }}>
                  <strong>Error:</strong> {processingError}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <input 
                type="file" 
                accept="video/mp4" 
                onChange={handleVideoUpload} 
                disabled={uploading || videoStatus === 'processing'}
              />
              
              {(videoStatus === 'uploaded' || videoStatus === 'failed') && (
                <button 
                  type="button" 
                  className="btn btn--primary" 
                  onClick={handleProcessHls}
                  disabled={uploading}
                >
                  Convert to HLS
                </button>
              )}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '0.9rem', opacity: 0.7, margin: 0 }}>
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
