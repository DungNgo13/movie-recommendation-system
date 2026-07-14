import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Tests for Movie Detail page DOM structure.
 *
 * Verifies that the movie banner, player, metadata, and ratings are
 * correctly positioned as siblings — not nested inside the banner.
 * This prevents the absolutely-positioned banner background from
 * expanding to the height of the full page content.
 */

// ── Mocks ─────────────────────────────────────────────────────────────

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'movie-1' }),
  };
});

// Mock useAuth
vi.mock('../hooks/useAuthHook', () => ({
  useAuth: () => ({ user: null, refreshUser: vi.fn() }),
}));

// Mock useFavorites
vi.mock('../hooks/useFavorites', () => ({
  useFavorites: () => ({
    favoriteIds: [],
    isFavorite: () => false,
    toggleFavorite: vi.fn(),
    loading: false,
  }),
}));

// Mock services
vi.mock('../services/movieService', () => ({
  getMovieById: vi.fn(),
}));

vi.mock('../services/ratingService', () => ({
  getMyRating: vi.fn().mockResolvedValue(null),
  rateMovie: vi.fn(),
}));

vi.mock('../services/recommendationService', () => ({
  getRecommendations: vi.fn().mockResolvedValue([]),
}));

vi.mock('../services/continueWatchingService', () => ({
  saveWatchProgress: vi.fn(),
  getWatchProgress: vi.fn().mockResolvedValue({ current_time_seconds: 0, is_completed: false }),
  saveGuestWatchProgress: vi.fn(),
  getGuestWatchProgressForMovie: vi.fn().mockReturnValue(null),
}));

// Mock HlsPlayer — renders a simple div so we can verify props
vi.mock('../components/HlsPlayer', () => ({
  default: (props: { src: string; poster?: string }) => (
    <div data-testid="mock-hls-player" data-src={props.src} data-poster={props.poster} />
  ),
}));

// Mock SourceAttribution
vi.mock('../components/SourceAttribution', () => ({
  default: () => <div data-testid="mock-source-attribution" />,
}));

// Mock LoadingSpinner
vi.mock('../components/LoadingSpinner', () => ({
  default: () => <div data-testid="mock-loading-spinner">Loading...</div>,
}));

// Mock ErrorMessage
vi.mock('../components/ErrorMessage', () => ({
  default: ({ message }: { message: string }) => <div data-testid="mock-error">{message}</div>,
}));

// Mock RecommendationCard
vi.mock('../components/RecommendationCard', () => ({
  default: () => <div data-testid="mock-recommendation-card" />,
}));

// Mock StarRating
vi.mock('../components/StarRating', () => ({
  default: () => <div data-testid="mock-star-rating" />,
}));

import MovieDetailPage from '../pages/MovieDetailPage';
import { getMovieById } from '../services/movieService';

const mockGetMovieById = getMovieById as ReturnType<typeof vi.fn>;

// ── Test data ─────────────────────────────────────────────────────────

const movieWithVideo = {
  id: 'movie-1',
  title: 'Test Movie',
  overview: 'A test movie overview.',
  release_date: '2024-01-15',
  genres: ['Action'],
  cast: ['Actor One'],
  keywords: ['test'],
  director: 'Director Name',
  poster_url: '/media/images/posters/test.jpg',
  backdrop_url: '/media/images/backdrops/test.jpg',
  video_status: 'ready',
  hls_playlist_url: '/media/videos/hls/movie-1/master.m3u8',
  video_progress: 0,
  video_step: null,
  processing_error: null,
  available_qualities: '720p,1080p',
};

const movieWithoutVideo = {
  ...movieWithVideo,
  video_status: 'no_video',
  hls_playlist_url: null,
};

const movieWithoutBackdrop = {
  ...movieWithoutVideo,
  backdrop_url: null,
};

// ── Helper ────────────────────────────────────────────────────────────

// Mock global fetch for the assets endpoint
const mockFetch = vi.fn();

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/movie/movie-1']}>
      <MovieDetailPage />
    </MemoryRouter>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('MovieDetailPage — DOM structure', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock global fetch for the assets endpoint and any other direct fetch calls
    globalThis.fetch = mockFetch;
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ items: [] }),
    });
  });

  it('renders .movie-banner when no video is ready', async () => {
    mockGetMovieById.mockResolvedValue(movieWithoutVideo);
    const { container } = renderPage();

    // Wait for async render
    await screen.findByText('Test Movie');

    const banner = container.querySelector('.movie-banner');
    expect(banner).not.toBeNull();
  });

  it('.movie-banner__bg is inside .movie-banner', async () => {
    mockGetMovieById.mockResolvedValue(movieWithoutVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const bg = container.querySelector('.movie-banner__bg');
    expect(bg).not.toBeNull();
    expect(bg?.parentElement?.classList.contains('movie-banner')).toBe(true);
  });

  it('.movie-banner__img is inside .movie-banner', async () => {
    mockGetMovieById.mockResolvedValue(movieWithoutVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const img = container.querySelector('.movie-banner__img');
    expect(img).not.toBeNull();
    expect(img?.closest('.movie-banner')).not.toBeNull();
  });

  it('.movie-player-container is NOT inside .movie-banner', async () => {
    mockGetMovieById.mockResolvedValue(movieWithVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const player = container.querySelector('.movie-player-container');
    expect(player).not.toBeNull();
    // Player must be a sibling, not a descendant of .movie-banner
    expect(player?.closest('.movie-banner')).toBeNull();
  });

  it('rating section is NOT inside .movie-banner', async () => {
    mockGetMovieById.mockResolvedValue(movieWithoutVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const rating = container.querySelector('.rating-section');
    expect(rating).not.toBeNull();
    expect(rating?.closest('.movie-banner')).toBeNull();
  });

  it('metadata block is NOT inside .movie-banner', async () => {
    mockGetMovieById.mockResolvedValue(movieWithoutVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const meta = container.querySelector('.movie-meta-block');
    expect(meta).not.toBeNull();
    expect(meta?.closest('.movie-banner')).toBeNull();
  });

  it('movie-banner does NOT appear when video is ready', async () => {
    mockGetMovieById.mockResolvedValue(movieWithVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const banner = container.querySelector('.movie-banner');
    expect(banner).toBeNull();
  });

  it('.movie-player-container appears when video is ready', async () => {
    mockGetMovieById.mockResolvedValue(movieWithVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const player = container.querySelector('.movie-player-container');
    expect(player).not.toBeNull();
  });

  it('player container has --backdrop modifier when backdrop exists', async () => {
    mockGetMovieById.mockResolvedValue(movieWithVideo);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const player = container.querySelector('.movie-player-container--backdrop');
    expect(player).not.toBeNull();
  });

  it('player container has --portrait-poster modifier when no backdrop', async () => {
    mockGetMovieById.mockResolvedValue({
      ...movieWithVideo,
      backdrop_url: null,
    });
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const player = container.querySelector('.movie-player-container--portrait-poster');
    expect(player).not.toBeNull();
  });

  it('banner renders safely when backdrop is missing', async () => {
    mockGetMovieById.mockResolvedValue(movieWithoutBackdrop);
    const { container } = renderPage();
    await screen.findByText('Test Movie');

    const banner = container.querySelector('.movie-banner');
    expect(banner).not.toBeNull();
    // Should still have bg and img elements
    expect(banner?.querySelector('.movie-banner__bg')).not.toBeNull();
    expect(banner?.querySelector('.movie-banner__img')).not.toBeNull();
  });

  it('HlsPlayer receives correct src and poster props', async () => {
    mockGetMovieById.mockResolvedValue(movieWithVideo);
    renderPage();
    await screen.findByText('Test Movie');

    const hlsPlayer = screen.getByTestId('mock-hls-player');
    expect(hlsPlayer.dataset.src).toBe('/media/videos/hls/movie-1/master.m3u8');
    // poster should be the resolved backdrop URL
    expect(hlsPlayer.dataset.poster).toBeTruthy();
  });
});
