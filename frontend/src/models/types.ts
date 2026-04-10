export interface Movie {
  id: string;
  title: string;
  overview: string | null;
  release_date: string | null;
  genres: string[] | null;
  director: string | null;
  poster_url: string | null;
  backdrop_url: string | null;
  video_url?: string | null;
  video_status?: string;
  video_progress?: number;
  video_step?: string;
  hls_playlist_url?: string | null;
  processing_error?: string | null;
  /** Comma-separated quality labels produced by FFmpeg, e.g. "360p,720p,1080p". Null if not yet encoded. */
  available_qualities?: string | null;
}

export interface MovieListItem {
    id: string;
    title: string;
    poster_url: string | null;
    backdrop_url?: string | null;
    release_year: number | null;
    genres?: string[] | null;
}

export interface PaginatedMovies {
    items: MovieListItem[];
    total: number;
    page: number;
    limit: number;
}
