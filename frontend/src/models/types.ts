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
  hls_playlist_url?: string | null;
  processing_error?: string | null;
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
