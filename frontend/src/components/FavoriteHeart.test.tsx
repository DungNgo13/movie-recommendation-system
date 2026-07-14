import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MovieCard from '../components/MovieCard';
import RecommendationCard from '../components/RecommendationCard';
import type { RecommendedMovie } from '../services/recommendationService';

/* ─── Helpers ─────────────────────────────────────────────────────── */

const baseMovie = {
  id: 'movie-1',
  title: 'Test Movie',
  poster_url: '/test-poster.jpg',
  backdrop_url: null,
};

const recMovie: RecommendedMovie = {
  id: 'rec-1',
  title: 'Recommended Movie',
  poster_url: '/rec-poster.jpg',
  release_year: 2024,
  score: 0.87,
  reason: 'Because you liked Action movies',
};

function renderMovieCard(overrides: Record<string, unknown> = {}) {
  const onToggleFavorite = vi.fn();
  const defaults = {
    movie: baseMovie,
    isFavorite: false,
    onToggleFavorite,
    favoriteLoading: false,
    ...overrides,
  };
  const result = render(
    <MemoryRouter>
      <MovieCard {...defaults} />
    </MemoryRouter>,
  );
  return { ...result, onToggleFavorite };
}

function renderRecCard(overrides: Record<string, unknown> = {}) {
  const onToggleFavorite = vi.fn();
  const defaults = {
    movie: recMovie,
    isFavorite: false,
    onToggleFavorite,
    favoriteLoading: false,
    ...overrides,
  };
  const result = render(
    <MemoryRouter>
      <RecommendationCard {...defaults} />
    </MemoryRouter>,
  );
  return { ...result, onToggleFavorite };
}

/* ─── MovieCard Tests ─────────────────────────────────────────────── */

describe('MovieCard — Favorite Heart', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a gray (outlined) heart when not favorited', () => {
    renderMovieCard({ isFavorite: false });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    expect(btn).toBeInTheDocument();
    // The SVG path should have fill="none" (outlined heart)
    const path = btn.querySelector('svg path');
    expect(path).toHaveAttribute('fill', 'none');
  });

  it('renders a red (filled) heart when favorited', () => {
    renderMovieCard({ isFavorite: true });
    const btn = screen.getByRole('button', { name: /remove test movie from favorites/i });
    expect(btn).toBeInTheDocument();
    expect(btn.classList.contains('movie-card__favorite-button--active')).toBe(true);
    // The SVG path should have fill="currentColor" (solid heart)
    const path = btn.querySelector('svg path');
    expect(path).toHaveAttribute('fill', 'currentColor');
  });

  it('calls onToggleFavorite with the correct movie ID when clicked', () => {
    const { onToggleFavorite } = renderMovieCard();
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    fireEvent.click(btn);
    expect(onToggleFavorite).toHaveBeenCalledTimes(1);
    expect(onToggleFavorite).toHaveBeenCalledWith('movie-1');
  });

  it('does not trigger card navigation when the heart is clicked', () => {
    renderMovieCard();
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    const clickEvent = new MouseEvent('click', { bubbles: true, cancelable: true });
    const preventDefaultSpy = vi.spyOn(clickEvent, 'preventDefault');
    const stopPropagationSpy = vi.spyOn(clickEvent, 'stopPropagation');
    btn.dispatchEvent(clickEvent);
    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(stopPropagationSpy).toHaveBeenCalled();
  });

  it('disables the button while the favorite request is pending', () => {
    renderMovieCard({ favoriteLoading: true });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    expect(btn).toBeDisabled();
  });

  it('does not call onToggleFavorite when disabled', () => {
    const { onToggleFavorite } = renderMovieCard({ favoriteLoading: true });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    fireEvent.click(btn);
    expect(onToggleFavorite).not.toHaveBeenCalled();
  });

  it('has accessible label "Add <title> to favorites" when not favorited', () => {
    renderMovieCard({ isFavorite: false });
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    expect(btn).toHaveAttribute('aria-label', 'Add Test Movie to favorites');
    expect(btn).toHaveAttribute('title', 'Add Test Movie to favorites');
  });

  it('has accessible label "Remove <title> from favorites" when favorited', () => {
    renderMovieCard({ isFavorite: true });
    const btn = screen.getByRole('button', { name: /remove test movie from favorites/i });
    expect(btn).toHaveAttribute('aria-label', 'Remove Test Movie from favorites');
    expect(btn).toHaveAttribute('title', 'Remove Test Movie from favorites');
  });

  it('renders the button as <button type="button"> for keyboard operability', () => {
    renderMovieCard();
    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    expect(btn.tagName).toBe('BUTTON');
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('preserves movie title and poster', () => {
    renderMovieCard();
    expect(screen.getByText('Test Movie')).toBeInTheDocument();
    const img = screen.getByAltText('Test Movie poster');
    expect(img).toHaveAttribute('src', '/test-poster.jpg');
  });
});

/* ─── RecommendationCard Tests ────────────────────────────────────── */

describe('RecommendationCard — Favorite Heart', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a gray (outlined) heart when not favorited', () => {
    renderRecCard({ isFavorite: false });
    const btn = screen.getByRole('button', { name: /add recommended movie to favorites/i });
    expect(btn).toBeInTheDocument();
    const path = btn.querySelector('svg path');
    expect(path).toHaveAttribute('fill', 'none');
  });

  it('renders a red (filled) heart when favorited', () => {
    renderRecCard({ isFavorite: true });
    const btn = screen.getByRole('button', { name: /remove recommended movie from favorites/i });
    expect(btn.classList.contains('movie-card__favorite-button--active')).toBe(true);
    const path = btn.querySelector('svg path');
    expect(path).toHaveAttribute('fill', 'currentColor');
  });

  it('calls onToggleFavorite with the correct movie ID when clicked', () => {
    const { onToggleFavorite } = renderRecCard();
    const btn = screen.getByRole('button', { name: /add recommended movie to favorites/i });
    fireEvent.click(btn);
    expect(onToggleFavorite).toHaveBeenCalledTimes(1);
    expect(onToggleFavorite).toHaveBeenCalledWith('rec-1');
  });

  it('disables the button while the favorite request is pending', () => {
    renderRecCard({ favoriteLoading: true });
    const btn = screen.getByRole('button', { name: /add recommended movie to favorites/i });
    expect(btn).toBeDisabled();
  });

  it('preserves recommendation reason and score', () => {
    renderRecCard();
    expect(screen.getByText('Because you liked Action movies')).toBeInTheDocument();
    expect(screen.getByText('87% match')).toBeInTheDocument();
  });

  it('shows "New for you" for cold-start recommendations', () => {
    const coldStartMovie: RecommendedMovie = {
      ...recMovie,
      score: 0,
      reason: 'Popular movie you might enjoy',
    };
    renderRecCard({ movie: coldStartMovie });
    expect(screen.getByText('New for you')).toBeInTheDocument();
  });
});

/* ─── FavoritesPage behavior (simulated via MovieCard) ────────────── */

describe('FavoritesPage — removing a favorite', () => {
  it('a favorited MovieCard toggles to unfavorited when heart is clicked', async () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <MemoryRouter>
        <MovieCard
          movie={baseMovie}
          isFavorite={true}
          onToggleFavorite={onToggle}
        />
      </MemoryRouter>,
    );

    // Initially favorited
    let btn = screen.getByRole('button', { name: /remove test movie from favorites/i });
    expect(btn.classList.contains('movie-card__favorite-button--active')).toBe(true);

    // Click to remove
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalledWith('movie-1');

    // Simulate state change (parent updates isFavorite to false)
    rerender(
      <MemoryRouter>
        <MovieCard
          movie={baseMovie}
          isFavorite={false}
          onToggleFavorite={onToggle}
        />
      </MemoryRouter>,
    );

    await waitFor(() => {
      btn = screen.getByRole('button', { name: /add test movie to favorites/i });
      expect(btn.classList.contains('movie-card__favorite-button--active')).toBe(false);
    });
  });
});

/* ─── Optimistic update rollback (simulated) ──────────────────────── */

describe('Optimistic update rollback', () => {
  it('restores previous state when toggle fails', async () => {
    const failingToggle = vi.fn().mockRejectedValue(new Error('Network error'));
    const { rerender } = render(
      <MemoryRouter>
        <MovieCard
          movie={baseMovie}
          isFavorite={false}
          onToggleFavorite={failingToggle}
        />
      </MemoryRouter>,
    );

    const btn = screen.getByRole('button', { name: /add test movie to favorites/i });
    fireEvent.click(btn);

    // The toggle was called
    expect(failingToggle).toHaveBeenCalledWith('movie-1');

    // Simulate parent rolling back (keeping isFavorite: false)
    rerender(
      <MemoryRouter>
        <MovieCard
          movie={baseMovie}
          isFavorite={false}
          onToggleFavorite={failingToggle}
        />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const restoredBtn = screen.getByRole('button', { name: /add test movie to favorites/i });
      expect(restoredBtn.classList.contains('movie-card__favorite-button--active')).toBe(false);
    });
  });
});
