import React, { useState, useEffect } from 'react';
import type { Movie } from '../../models';
import type { MovieFormData } from '../../services/movieService';

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (movie) {
      setTitle(movie.title);
      setOverview(movie.overview || '');
      setReleaseDate(movie.release_date || '');
      setDirector(movie.director || '');
      setPosterUrl(movie.poster_url || '');
      setBackdropUrl(movie.backdrop_url || '');
    }
  }, [movie]);

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
