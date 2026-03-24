import { Movie, PaginatedMovies } from '../models/movie';

const API_BASE_URL = 'http://localhost:8000/api/v1'; // Assuming the backend runs on port 8000

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
