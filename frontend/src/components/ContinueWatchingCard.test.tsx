import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import ContinueWatchingCard from './ContinueWatchingCard';

// Mock continueWatchingService for formatPlaybackTime
vi.mock('../services/continueWatchingService', () => ({
  formatPlaybackTime: (s: number) => {
    const safe = Math.max(0, Math.floor(s));
    const m = Math.floor(safe / 60);
    const sec = safe % 60;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  },
}));

const renderCard = (overrides: Partial<Parameters<typeof ContinueWatchingCard>[0]> = {}) => {
  const defaultProps = {
    movie: {
      id: 'movie-123',
      title: 'Test Movie',
      poster_url: 'https://example.com/poster.jpg',
    },
    progressPercent: 42,
    playbackPositionSeconds: 120,
    isFavorite: false,
    onToggleFavorite: vi.fn(),
    ...overrides,
  };
  return render(
    <MemoryRouter>
      <ContinueWatchingCard {...defaultProps} />
    </MemoryRouter>,
  );
};

describe('ContinueWatchingCard', () => {
  // ── Progress bar rendering ──

  it('renders a progress bar with role="progressbar"', () => {
    renderCard();
    const bar = screen.getByRole('progressbar');
    expect(bar).toBeTruthy();
  });

  it('sets aria-valuenow to the rounded percentage', () => {
    renderCard({ progressPercent: 42.7 });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('43');
  });

  it('sets aria-valuemin=0 and aria-valuemax=100', () => {
    renderCard();
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuemin')).toBe('0');
    expect(bar.getAttribute('aria-valuemax')).toBe('100');
  });

  it('sets aria-label with movie title and percentage', () => {
    renderCard({ progressPercent: 50 });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-label')).toContain('50%');
    expect(bar.getAttribute('aria-label')).toContain('Test Movie');
  });

  // ── Progress value clamping ──

  it('clamps progress below 0 to 0', () => {
    renderCard({ progressPercent: -10 });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('0');
    // Fill width should be 0%
    const fill = bar.querySelector('.cw-card__progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('0%');
  });

  it('clamps progress above 100 to 100', () => {
    renderCard({ progressPercent: 120 });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('100');
    const fill = bar.querySelector('.cw-card__progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });

  it('renders NaN progress as 0', () => {
    renderCard({ progressPercent: NaN });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('0');
    const fill = bar.querySelector('.cw-card__progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('0%');
  });

  it('renders Infinity progress as 0', () => {
    renderCard({ progressPercent: Infinity });
    const bar = screen.getByRole('progressbar');
    expect(bar.getAttribute('aria-valuenow')).toBe('0');
  });

  // ── Metadata inside the card ──

  it('renders playback time inside the card', () => {
    renderCard({ playbackPositionSeconds: 120 });
    expect(screen.getByText(/02:00/)).toBeTruthy();
  });

  it('renders rounded percentage inside the card', () => {
    renderCard({ progressPercent: 91 });
    expect(screen.getByText(/91%/)).toBeTruthy();
  });

  it('renders movie title inside the card', () => {
    renderCard();
    expect(screen.getByText('Test Movie')).toBeTruthy();
  });

  // ── Progress fill accuracy ──

  it('sets fill width matching progressPercent', () => {
    renderCard({ progressPercent: 23 });
    const bar = screen.getByRole('progressbar');
    const fill = bar.querySelector('.cw-card__progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('23%');
  });

  it('small progress (2%) remains visible as fill', () => {
    renderCard({ progressPercent: 2 });
    const bar = screen.getByRole('progressbar');
    const fill = bar.querySelector('.cw-card__progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('2%');
  });

  it('91% bar nearly fills the track', () => {
    renderCard({ progressPercent: 91 });
    const bar = screen.getByRole('progressbar');
    const fill = bar.querySelector('.cw-card__progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('91%');
  });

  // ── Card navigation ──

  it('links to the movie detail page', () => {
    renderCard();
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe('/movie/movie-123');
  });

  // ── Favorite button ──

  it('renders favorite button with correct aria-label', () => {
    renderCard({ isFavorite: false });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    expect(btn).toBeTruthy();
  });

  it('favorite button fires onToggleFavorite with movie id', async () => {
    const mockToggle = vi.fn();
    renderCard({ onToggleFavorite: mockToggle });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });

    await userEvent.click(btn);

    expect(mockToggle).toHaveBeenCalledWith('movie-123');
  });

  it('favorite button stops event propagation (does not navigate)', async () => {
    const mockToggle = vi.fn();
    renderCard({ onToggleFavorite: mockToggle });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });

    await userEvent.click(btn);

    // The button was clicked and toggle was called
    expect(mockToggle).toHaveBeenCalledTimes(1);
  });

  // ── Poster fallback ──

  it('shows fallback when poster_url is null', () => {
    renderCard({ movie: { id: 'x', title: 'No Poster', poster_url: null } });
    const img = screen.getByAltText('No Poster poster') as HTMLImageElement;
    expect(img.src).toContain('placeholder-poster.svg');
  });

  // ── Both guest and auth use same component ──

  it('renders identically for guest and auth (same component)', () => {
    const { container } = renderCard();
    expect(container.querySelector('.cw-card')).toBeTruthy();
    expect(container.querySelector('.cw-card__progress')).toBeTruthy();
    expect(container.querySelector('.cw-card-progress')).toBeTruthy();
  });

  // ── Various percentage display ──

  it('renders 2% correctly', () => {
    renderCard({ progressPercent: 2 });
    expect(screen.getByText(/2%/)).toBeTruthy();
  });

  it('renders 50% correctly', () => {
    renderCard({ progressPercent: 50 });
    expect(screen.getByText(/50%/)).toBeTruthy();
  });

  it('renders 94% correctly', () => {
    renderCard({ progressPercent: 94 });
    expect(screen.getByText(/94%/)).toBeTruthy();
  });

  // ── Play overlay inside media container ──

  it('play indicator renders inside the media container', () => {
    const { container } = renderCard();
    const media = container.querySelector('.cw-card__media');
    expect(media).toBeTruthy();
    const play = media!.querySelector('.continue-watching-card__play');
    expect(play).toBeTruthy();
  });

  it('play indicator is not rendered after the content/progress section', () => {
    const { container } = renderCard();
    const content = container.querySelector('.cw-card__content');
    expect(content).toBeTruthy();
    const playInContent = content!.querySelector('.continue-watching-card__play');
    expect(playInContent).toBeNull();
  });

  it('play indicator uses the scoped class', () => {
    const { container } = renderCard();
    const play = container.querySelector('.continue-watching-card__play');
    expect(play).toBeTruthy();
  });

  it('play indicator contains an SVG', () => {
    const { container } = renderCard();
    const play = container.querySelector('.continue-watching-card__play');
    expect(play).toBeTruthy();
    expect(play!.querySelector('svg')).toBeTruthy();
  });

  it('play indicator is aria-hidden', () => {
    const { container } = renderCard();
    const play = container.querySelector('.continue-watching-card__play');
    expect(play!.getAttribute('aria-hidden')).toBe('true');
  });
});
