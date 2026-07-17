export interface Movie {
  id: string;
  title: string;
  overview: string | null;
  release_date: string | null;
  genres: string[] | null;
  cast: string[] | null;         // top-billed actor names — used by TF-IDF engine
  keywords: string[] | null;     // thematic tags — used by TF-IDF engine
  director: string | null;
  poster_url: string | null;
  backdrop_url: string | null;

  // Vietnamese display metadata (optional)
  title_vi?: string | null;
  overview_vi?: string | null;
  keyword_labels_vi?: Record<string, string> | null;
  video_url?: string | null;
  video_status?: string;
  video_progress?: number;
  video_step?: string;
  hls_playlist_url?: string | null;
  processing_error?: string | null;
  /** Comma-separated quality labels produced by FFmpeg, e.g. "360p,720p,1080p". Null if not yet encoded. */
  available_qualities?: string | null;
  /** 0–100 data-completeness score computed on-the-fly by the backend schema. Not stored in DB. */
  quality_score?: number;

  // Source & license tracking
  source_name?: string | null;
  source_url?: string | null;
  license_type?: string | null;
  license_url?: string | null;
  attribution?: string | null;
  is_public_domain?: boolean;
  media_rights_status?: string | null;
}

export interface MovieListItem {
    id: string;
    title: string;
    title_vi?: string | null;
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

export interface MovieAsset {
  id: string;
  movie_id: string;
  asset_type: string;
  url: string | null;
  source_name: string | null;
  source_url: string | null;
  license_type: string | null;
  license_url: string | null;
  attribution: string | null;
  is_public_domain: boolean;
  media_rights_status: string;
  created_at: string;
  /** Set by the backend when status is 'unknown' — frontend should show placeholder */
  _placeholder?: boolean;
}
