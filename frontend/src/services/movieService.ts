import type { Movie, PaginatedMovies } from '../models';

const API_BASE_URL = 'http://localhost:8000/api/v1'; // Assuming the backend runs on port 8000

export interface MovieFormData {
  title: string;
  overview?: string | null;
  release_date?: string | null;
  genres?: string[] | null;
  director?: string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
}

export const getMovies = async (page = 1, limit = 20): Promise<PaginatedMovies> => {
  const response = await fetch(`${API_BASE_URL}/movies?page=${page}&limit=${limit}`);
  if (!response.ok) {
    throw new Error('Failed to fetch movies');
  }
  return response.json();
};

export const getMovieById = async (id: string): Promise<Movie> => {
  const response = await fetch(`${API_BASE_URL}/movies/${id}`);
  if (!response.ok) {
    throw new Error('Failed to fetch movie');
  }
  return response.json();
};

export const createMovie = async (data: MovieFormData): Promise<Movie> => {
  const response = await fetch(`${API_BASE_URL}/movies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to create movie');
  }
  return response.json();
};

export const updateMovie = async (id: string, data: MovieFormData): Promise<Movie> => {
  const response = await fetch(`${API_BASE_URL}/movies/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to update movie');
  }
  return response.json();
};

export const deleteMovie = async (id: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/movies/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete movie');
  }
};

