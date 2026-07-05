import type { Movie, PaginatedMovies } from '../models';
import { getToken } from './authService';

import { API_BASE_URL } from '../config';

export interface MovieFormData {
  title: string;
  overview?: string | null;
  release_date?: string | null;
  genres?: string[] | null;
  cast?: string[] | null;       // actor names → fed into TF-IDF recommendation engine
  keywords?: string[] | null;   // thematic tags  → fed into TF-IDF recommendation engine
  director?: string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;

  // Source & license (movie-level metadata)
  source_name?: string | null;
  source_url?: string | null;
  license_type?: string | null;
  license_url?: string | null;
  attribution?: string | null;
  media_rights_status?: string | null;
  is_public_domain?: boolean | null;
}

export interface MovieFilters {
  search?: string;
  genre?: string;
  year?: number | null;
}

export const getMovies = async (
  page = 1,
  limit = 20,
  filters?: MovieFilters,
): Promise<PaginatedMovies> => {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('limit', String(limit));

  if (filters?.search) {
    params.set('search', filters.search);
  }
  if (filters?.genre) {
    params.set('genre', filters.genre);
  }
  if (filters?.year != null) {
    params.set('year', String(filters.year));
  }

  const response = await fetch(`${API_BASE_URL}/movies?${params.toString()}`);
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
    // Content-Type is required even for an empty-body POST so FastAPI doesn't
    // reject the request with a 422 Unprocessable Entity on some versions.
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    // Parse the backend JSON error body so callers get the exact detail string.
    const errorData = await response.json().catch(() => null);
    const message   = errorData?.detail || `Request failed (HTTP ${response.status})`;
    const err       = new Error(message) as Error & { status?: number };
    err.status      = response.status;   // callers check .status === 401 / 409 etc.
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
