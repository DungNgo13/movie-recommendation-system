import type { Movie, PaginatedMovies } from '../models';
import { getToken } from './authService';

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
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}/movies`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to create movie');
  }
  return response.json();
};

export const updateMovie = async (id: string, data: MovieFormData): Promise<Movie> => {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}/movies/${id}`, {
    method: 'PUT',
    headers: { 
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to update movie');
  }
  return response.json();
};

export const deleteMovie = async (id: string): Promise<void> => {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}/movies/${id}`, {
    method: 'DELETE',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error('Failed to delete movie');
  }
};

export const uploadMovieVideo = async (
  id: string,
  file: File,
  onProgress?: (percent: number) => void
): Promise<Movie> => {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });
    }

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error('Failed to parse server response'));
        }
      } else {
        let detail = 'Failed to upload video';
        try {
          detail = JSON.parse(xhr.responseText)?.detail ?? detail;
        } catch { /* ignore */ }
        reject(new Error(detail));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
    xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));

    xhr.open('POST', `${API_BASE_URL}/movies/${id}/video`);
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  });
};

export const processMovieVideo = async (id: string): Promise<{ message: string }> => {
  const token = getToken();

  const response = await fetch(`${API_BASE_URL}/movies/${id}/process-hls`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    // Attach the HTTP status to the error so callers can handle 401 specially
    const errorData = await response.json().catch(() => null);
    const err = new Error(errorData?.detail || 'Failed to trigger processing') as Error & { status?: number };
    err.status = response.status;
    throw err;
  }
  return response.json();
};

export const getMovieProcessingStatus = async (id: string): Promise<{
  video_status: string;
  video_progress: number;
  video_step: string | null;
  processing_error: string | null;
  hls_playlist_url: string | null;
  available_qualities: string | null;
}> => {
  const response = await fetch(`${API_BASE_URL}/movies/${id}/status`);

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || 'Failed to fetch status');
  }
  return response.json();
};

export const uploadMovieImage = async (id: string, file: File, type: 'poster' | 'backdrop'): Promise<Movie> => {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/movies/${id}/${type}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `Failed to upload ${type}`);
  }
  return response.json();
};

export const cancelEncodeMovie = async (id: string): Promise<{ cancelled: boolean; detail: string }> => {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}/movies/${id}/cancel-encode`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(body?.detail || 'Failed to cancel encode');
  }
  return body;
};
