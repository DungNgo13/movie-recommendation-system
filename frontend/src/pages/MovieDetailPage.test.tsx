import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

// Mock useAuth — mutable so metadata tests can set an authenticated user
let mockUser: { email: string } | null = null;
vi.mock('../hooks/useAuthHook', () => ({
  useAuth: () => ({ user: mockUser, refreshUser: vi.fn() }),
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
  getMoviesByMetadata: vi.fn(),
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
  saveWatchProgressBeacon: vi.fn(),
  getWatchProgress: vi.fn().mockResolvedValue({ current_time_seconds: 0, is_completed: false }),
  saveGuestWatchProgress: vi.fn(),
  getGuestWatchProgressForMovie: vi.fn().mockReturnValue(null),
  isWatchCompleted: (p: number) => p >= 95,
  formatPlaybackTime: (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  },
  COMPLETION_THRESHOLD: 95,
  GUEST_HISTORY_EVENT: 'guest-watch-history-updated',
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
  default: ({ movie }: { movie: { title: string } }) => (
    <div data-testid="mock-recommendation-card">{movie.title}</div>
  ),
}));

// Mock MovieCard
vi.mock('../components/MovieCard', () => ({
  default: ({ movie }: { movie: { title: string } }) => (
    <div data-testid="mock-movie-card">{movie.title}</div>
  ),
}));

// Mock StarRating
vi.mock('../components/StarRating', () => ({
  default: () => <div data-testid="mock-star-rating" />,
}));

import MovieDetailPage from '../pages/MovieDetailPage';
import { getMovieById, getMoviesByMetadata } from '../services/movieService';

const mockGetMovieById = getMovieById as ReturnType<typeof vi.fn>;
const mockGetMoviesByMetadata = getMoviesByMetadata as ReturnType<typeof vi.fn>;

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
    mockUser = null;  // default to anonymous for DOM structure tests
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

// ── Metadata Discovery tests ────────────────────────────────────────

import { getRecommendations } from '../services/recommendationService';
const mockGetRecommendations = getRecommendations as ReturnType<typeof vi.fn>;

const movieWithMetadata = {
  ...movieWithoutVideo,
  director: 'Pexels Creator',
  cast: ['Drone Camera', 'Forest Landscape'],
  keywords: ['drone', 'forest', 'green forest'],
};

const metadataResults = [
  { id: 'meta-1', title: 'Nature Walks', poster_url: null, release_year: 2023, genres: [] },
  { id: 'meta-2', title: 'City Lights', poster_url: null, release_year: 2022, genres: [] },
];

const personalizedResults = [
  { id: 'rec-1', title: 'Rec Movie 1', poster_url: null, release_year: 2020, score: 0.85, reason: 'Based on your ratings' },
  { id: 'rec-2', title: 'Rec Movie 2', poster_url: null, release_year: 2021, score: 0.72, reason: 'Similar genres' },
];

describe('MovieDetailPage — Metadata Discovery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = { email: 'test@example.com' }; // authenticated by default
    globalThis.fetch = mockFetch;
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ items: [] }),
    });
    mockGetMoviesByMetadata.mockResolvedValue(metadataResults);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
  });

  // ── Interactive controls ──

  it('Director renders as an interactive button', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    const directorBtn = screen.getByRole('button', { name: /show movies directed by pexels creator/i });
    expect(directorBtn).toBeTruthy();
    expect(directorBtn.textContent).toBe('Pexels Creator');
  });

  it('Cast entries render as interactive chips', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    const droneCameraBtn = screen.getByRole('button', { name: /show movies featuring drone camera/i });
    expect(droneCameraBtn).toBeTruthy();

    const forestBtn = screen.getByRole('button', { name: /show movies featuring forest landscape/i });
    expect(forestBtn).toBeTruthy();
  });

  it('Keywords render as interactive chips', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    const droneBtn = screen.getByRole('button', { name: /show movies tagged drone/i });
    expect(droneBtn).toBeTruthy();
    expect(droneBtn.textContent).toBe('#drone');

    const forestBtn = screen.getByRole('button', { name: /show movies tagged forest/i });
    expect(forestBtn).toBeTruthy();
  });

  // ── Clicking metadata triggers fetch ──

  it('clicking Director calls getMoviesByMetadata with director filter', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    const dirBtn = screen.getByRole('button', { name: /show movies directed by pexels creator/i });
    await userEvent.click(dirBtn);

    // Wait for metadata effect to fire (filter change triggers fetch)
    await vi.waitFor(() => {
      expect(mockGetMoviesByMetadata).toHaveBeenCalledWith(
        { type: 'director', value: 'Pexels Creator' },
        expect.objectContaining({ excludeMovieId: 'movie-1' }),
      );
    });
  });

  it('clicking keyword calls getMoviesByMetadata with keyword filter', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    const kwBtn = screen.getByRole('button', { name: /show movies tagged forest$/i });
    await userEvent.click(kwBtn);

    // Wait for metadata effect to fire (filter change triggers fetch)
    await vi.waitFor(() => {
      expect(mockGetMoviesByMetadata).toHaveBeenCalledWith(
        { type: 'keyword', value: 'forest' },
        expect.objectContaining({ excludeMovieId: 'movie-1' }),
      );
    });
  });

  // ── Section title changes ──

  it('metadata mode changes section title for director', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    renderPage();
    await screen.findByText('Recommended for You');

    const dirBtn = screen.getByRole('button', { name: /show movies directed by pexels creator/i });
    await userEvent.click(dirBtn);

    await screen.findByText('More movies by Pexels Creator');
  });

  it('metadata mode changes section title for keyword', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    renderPage();
    await screen.findByText('Recommended for You');

    const kwBtn = screen.getByRole('button', { name: /show movies tagged drone/i });
    await userEvent.click(kwBtn);

    await screen.findByText('Movies tagged #drone');
  });

  it('metadata mode changes section title for cast', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    renderPage();
    await screen.findByText('Recommended for You');

    const castBtn = screen.getByRole('button', { name: /show movies featuring drone camera/i });
    await userEvent.click(castBtn);

    await screen.findByText('Movies featuring Drone Camera');
  });

  // ── Metadata results replace personalized cards ──

  it('metadata results display MovieCards, not RecommendationCards', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    renderPage();
    await screen.findByText('Recommended for You');

    // Before click: recommendation cards visible
    expect(screen.getAllByTestId('mock-recommendation-card').length).toBe(2);

    const dirBtn = screen.getByRole('button', { name: /show movies directed by pexels creator/i });
    await userEvent.click(dirBtn);

    // After click: movie cards visible, no recommendation cards
    await screen.findByText('Nature Walks');
    expect(screen.getAllByTestId('mock-movie-card').length).toBe(2);
    expect(screen.queryAllByTestId('mock-recommendation-card').length).toBe(0);
  });

  // ── Clear filter restores personalized ──

  it('clear filter restores cached personalized cards', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    renderPage();
    await screen.findByText('Recommended for You');

    // Activate metadata
    const dirBtn = screen.getByRole('button', { name: /show movies directed by pexels creator/i });
    await userEvent.click(dirBtn);
    await screen.findByText('More movies by Pexels Creator');

    // Clear
    const clearBtn = screen.getByRole('button', { name: /back to personalized/i });
    await userEvent.click(clearBtn);

    // Personalized cards restored
    await screen.findByText('Recommended for You');
    expect(screen.getAllByTestId('mock-recommendation-card').length).toBe(2);
  });

  // ── Empty state ──

  it('empty metadata result shows correct empty state', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    mockGetMoviesByMetadata.mockResolvedValue([]);
    renderPage();
    await screen.findByText('Recommended for You');

    const kwBtn = screen.getByRole('button', { name: /show movies tagged forest$/i });
    await userEvent.click(kwBtn);

    await screen.findByText(/no other movies found with keyword #forest/i);
  });

  // ── Error state ──

  it('metadata API failure does not erase personalized results', async () => {
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    mockGetRecommendations.mockResolvedValue(personalizedResults);
    mockGetMoviesByMetadata.mockRejectedValue(new Error('Network error'));
    renderPage();
    await screen.findByText('Recommended for You');

    const dirBtn = screen.getByRole('button', { name: /show movies directed by pexels creator/i });
    await userEvent.click(dirBtn);

    // Error shown
    await screen.findByText(/unable to load movies for pexels creator/i);

    // Clear restores personalized — use first match (header has one, error body has another)
    const clearBtns = screen.getAllByRole('button', { name: /back to personalized/i });
    await userEvent.click(clearBtns[0]);

    await screen.findByText('Recommended for You');
    expect(screen.getAllByTestId('mock-recommendation-card').length).toBe(2);
  });

  // ── Anonymous user ──

  it('anonymous users can use metadata discovery', async () => {
    mockUser = null; // anonymous
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    const kwBtn = screen.getByRole('button', { name: /show movies tagged drone/i });
    await userEvent.click(kwBtn);

    await screen.findByText('Movies tagged #drone');
    expect(mockGetMoviesByMetadata).toHaveBeenCalled();
  });

  it('anonymous users do not call /recommendations/me', async () => {
    mockUser = null; // anonymous
    mockGetMovieById.mockResolvedValue(movieWithMetadata);
    renderPage();
    await screen.findByText('Test Movie');

    // When user is null, getRecommendations is NOT called at all
    // The component short-circuits: if (!user) { setPersonalizedRecs([]); return; }
    expect(mockGetRecommendations).not.toHaveBeenCalled();
  });
});
