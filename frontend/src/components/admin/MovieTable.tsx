import React from 'react';
import type { Movie } from '../../models';

interface MovieTableProps {
  movies: Movie[];
  onEdit: (movie: Movie) => void;
  onDelete: (movie: Movie) => void;
}

const MovieTable: React.FC<MovieTableProps> = ({ movies, onEdit, onDelete }) => {
  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Director</th>
            <th>Release Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {movies.map((movie) => (
            <tr key={movie.id}>
              <td>{movie.title}</td>
              <td>{movie.director || '—'}</td>
              <td>{movie.release_date || '—'}</td>
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
