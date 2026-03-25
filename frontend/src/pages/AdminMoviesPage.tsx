import React, { useState, useEffect, useCallback } from 'react';
import MovieTable from '../components/admin/MovieTable';
import MovieForm from '../components/admin/MovieForm';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import type { Movie } from '../models';
import type { MovieFormData } from '../services/movieService';
import {
  getMovies,
  createMovie,
  updateMovie,
  deleteMovie,
  getMovieById,
} from '../services/movieService';

const AdminMoviesPage: React.FC = () => {
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingMovie, setEditingMovie] = useState<Movie | null>(null);
  const [deletingMovie, setDeletingMovie] = useState<Movie | null>(null);

  const fetchMovies = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMovies(1, 100);
      const detailed = await Promise.all(
        data.items.map((item) => getMovieById(item.id)),
      );
      setMovies(detailed);
    } catch {
      setError('Failed to fetch movies.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMovies();
  }, [fetchMovies]);

  const handleCreate = async (formData: MovieFormData) => {
    try {
      await createMovie(formData);
      setShowForm(false);
      await fetchMovies();
    } catch {
      setError('Failed to create movie.');
    }
  };

  const handleUpdate = async (formData: MovieFormData) => {
    if (!editingMovie) return;
    try {
      await updateMovie(editingMovie.id, formData);
      setEditingMovie(null);
      setShowForm(false);
      await fetchMovies();
    } catch {
      setError('Failed to update movie.');
    }
  };

  const handleDeleteRequest = (movie: Movie) => {
    setDeletingMovie(movie);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingMovie) return;
    try {
      await deleteMovie(deletingMovie.id);
      setDeletingMovie(null);
      await fetchMovies();
    } catch {
      setError('Failed to delete movie.');
      setDeletingMovie(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeletingMovie(null);
  };

  const handleEdit = (movie: Movie) => {
    setEditingMovie(movie);
    setShowForm(true);
  };

  const handleCancel = () => {
    setEditingMovie(null);
    setShowForm(false);
  };

  const handleAdd = () => {
    setEditingMovie(null);
    setShowForm(true);
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="admin-page">
      <span className="admin-badge">Admin Mode</span>

      <div className="admin-header">
        <h1>🎬 Movie Management</h1>
        {!showForm && (
          <button className="btn btn--primary" onClick={handleAdd}>
            + Add Movie
          </button>
        )}
      </div>

      {error && <ErrorMessage message={error} />}

      {showForm ? (
        <MovieForm
          movie={editingMovie}
          onSubmit={editingMovie ? handleUpdate : handleCreate}
          onCancel={handleCancel}
        />
      ) : (
        <>
          {movies.length === 0 ? (
            <div className="admin-empty">
              <p>📭 No movies available.</p>
              <button className="btn btn--primary" onClick={handleAdd}>
                + Add Movie
              </button>
            </div>
          ) : (
            <MovieTable
              movies={movies}
              onEdit={handleEdit}
              onDelete={handleDeleteRequest}
            />
          )}
        </>
      )}

      {deletingMovie && (
        <div className="confirm-overlay">
          <div className="confirm-dialog">
            <h3>Delete Movie</h3>
            <p>
              Are you sure you want to delete <strong>"{deletingMovie.title}"</strong>?
              This action cannot be undone.
            </p>
            <div className="confirm-actions">
              <button className="btn btn--delete" onClick={handleDeleteConfirm}>
                Delete
              </button>
              <button className="btn btn--secondary" onClick={handleDeleteCancel}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminMoviesPage;
