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
  getMovieProcessingStatus,
  cancelEncodeMovie,
  processMovieVideo,
} from '../services/movieService';

const AdminMoviesPage: React.FC = () => {
  const [movies, setMovies]           = useState<Movie[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  // Toast for session-expired (401) — shown as a dismissible amber banner
  const [sessionToast, setSessionToast] = useState<string | null>(null);
  const [showForm, setShowForm]       = useState(false);
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

  // Poll status for any movie currently in the 'processing' state.
  // Updates the individual row in-place without a full list reload.
  useEffect(() => {
    const processingIds = movies
      .filter((m) => m.video_status === 'processing')
      .map((m) => m.id);

    if (processingIds.length === 0) return;

    const interval = window.setInterval(async () => {
      const updates = await Promise.allSettled(
        processingIds.map((id) => getMovieProcessingStatus(id)),
      );
      setMovies((prev) =>
        prev.map((m) => {
          const idx = processingIds.indexOf(m.id);
          if (idx === -1) return m;
          const result = updates[idx];
          if (result.status === 'fulfilled') {
            const s = result.value;
            return {
              ...m,
              video_status: s.video_status,
              video_progress: s.video_progress ?? m.video_progress,
              video_step: s.video_step ?? m.video_step,
              hls_playlist_url: s.hls_playlist_url ?? m.hls_playlist_url,
              processing_error: s.processing_error ?? m.processing_error,
              available_qualities: s.available_qualities ?? m.available_qualities,
            };
          }
          return m;
        }),
      );
    }, 5000);

    return () => clearInterval(interval);
  }, [movies]);

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

  // Called when the user clicks "⬛ Stop" on a processing movie.
  // Optimistically patches the row to "ready" / Cancelled, then confirms
  // via a status refresh so the UI reflects the true DB state.
  const handleCancelEncode = async (movie: Movie) => {
    try {
      await cancelEncodeMovie(movie.id);
      // Optimistic update — flip this row immediately so the button disappears
      setMovies((prev) =>
        prev.map((m) =>
          m.id === movie.id
            ? { ...m, video_status: 'ready', video_step: 'Cancelled', video_progress: 0, available_qualities: undefined }
            : m
        )
      );
      // Then confirm with a live status fetch
      const fresh = await getMovieProcessingStatus(movie.id);
      setMovies((prev) =>
        prev.map((m) =>
          m.id === movie.id
            ? { ...m, video_status: fresh.video_status, video_step: fresh.video_step ?? undefined, video_progress: fresh.video_progress, available_qualities: fresh.available_qualities ?? undefined }
            : m
        )
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to cancel encode';
      setError(msg);
    }
  };

  // Called by MovieTable when the admin clicks "▶ Start Encoding" on a row.
  // Optimistically transitions the row to "processing" immediately so the UI
  // responds before the background task starts, then handles auth errors clearly.
  const handleStartEncode = async (movie: Movie) => {
    // Optimistic update — show the encoding spinner right away
    setMovies((prev) =>
      prev.map((m) =>
        m.id === movie.id
          ? { ...m, video_status: 'processing', available_qualities: 'Processing...', video_progress: 0, video_step: 'Queued' }
          : m
      )
    );

    try {
      await processMovieVideo(movie.id);
    } catch (err: unknown) {
      const typedErr = err as Error & { status?: number };

      // 401 — session expired: show a prominent toast and do NOT redirect
      // silently; let the user finish what they were doing and choose to log in.
      if (typedErr.status === 401) {
        setSessionToast('Your session has expired. Please log in again to continue encoding.');
        // Roll back the optimistic update
        setMovies((prev) =>
          prev.map((m) =>
            m.id === movie.id
              ? { ...m, video_status: movie.video_status, available_qualities: movie.available_qualities, video_progress: movie.video_progress, video_step: movie.video_step }
              : m
          )
        );
        return;
      }

      // 409 — already encoding (race condition from double-click)
      if (typedErr.status === 409) {
        // The encode is running anyway — just refresh the row status
        const fresh = await getMovieProcessingStatus(movie.id).catch(() => null);
        if (fresh) {
          setMovies((prev) =>
            prev.map((m) =>
              m.id === movie.id ? { ...m, video_status: fresh.video_status, available_qualities: fresh.available_qualities } : m
            )
          );
        }
        return;
      }

      // Other errors — show in the page error banner and roll back the row
      const msg = typedErr.message || 'Failed to start encoding';
      setError(msg);
      setMovies((prev) =>
        prev.map((m) =>
          m.id === movie.id
            ? { ...m, video_status: movie.video_status, available_qualities: movie.available_qualities }
            : m
        )
      );
    }
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

      {/* ── Session-expired toast (401) ───────────────────────────────── */}
      {sessionToast && (
        <div className="session-toast">
          <span>{sessionToast}</span>
          <button
            onClick={() => { setSessionToast(null); window.location.href = '/login'; }}
            className="session-toast__login-btn"
          >
            Log in
          </button>
          <button
            onClick={() => setSessionToast(null)}
            className="session-toast__dismiss-btn"
            aria-label="Dismiss"
          >×</button>
        </div>
      )}

      <div className="admin-header">
        <h1>Movie Management</h1>
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
              <p>No movies available.</p>
              <button className="btn btn--primary" onClick={handleAdd}>
                + Add Movie
              </button>
            </div>
          ) : (
        <MovieTable
              movies={movies}
              onEdit={handleEdit}
              onDelete={handleDeleteRequest}
              onCancelEncode={handleCancelEncode}
              onStartEncode={handleStartEncode}
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
