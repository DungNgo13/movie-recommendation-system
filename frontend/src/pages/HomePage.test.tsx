import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// ── Controllable i18n mock ─────────────────────────────────────────────

let mockLanguage = 'en';

import type { MovieListItem } from '../models';

// Translation data matching the real locale files
const translations: Record<string, Record<string, string>> = {
  en: {
    'movies:hero.watchNow': 'Watch Now',
    'movies:hero.moreInfo': 'More Info',
    'movies:hero.watchMovie': 'Watch {{title}}',
    'movies:hero.moreInfoMovie': 'More info about {{title}}',
    'movies:hero.backdropAlt': '{{title}} featured backdrop',
    'movies:home.searchPlaceholder': 'Search by title...',
    'movies:home.allGenres': 'All Genres',
    'movies:home.allYears': 'All Years',
    'movies:home.sort.titleAsc': 'Title A–Z',
    'movies:home.sort.titleDesc': 'Title Z–A',
    'movies:home.sort.yearDesc': 'Newest First',
    'movies:home.sort.yearAsc': 'Oldest First',
    'movies:home.moviesByGenre': 'Movies by Genre',
    'movies:home.noMoviesFound': 'No movies found',
    'movies:home.noMoviesDesc': 'Try adjusting your filters or search query to discover more movies.',
    'movies:home.resetFilters': 'Reset Filters',
    'movies:continueWatching.title': 'Continue Watching',
    'movies:continueWatching.resume': 'Resume',
    'movies:continueWatching.progress': '▶ {{time}} · {{percent}}%',
    'recommendation:title': 'Recommended For You',
    'recommendation:match': '{{percent}}% match',
    'recommendation:new_for_you': 'New for you',
  },
  vi: {
    'movies:hero.watchNow': 'Xem ngay',
    'movies:hero.moreInfo': 'Xem thông tin',
    'movies:hero.watchMovie': 'Xem {{title}}',
    'movies:hero.moreInfoMovie': 'Xem thông tin về {{title}}',
    'movies:hero.backdropAlt': 'Ảnh nền phim {{title}}',
    'movies:home.searchPlaceholder': 'Tìm kiếm theo tiêu đề...',
    'movies:home.allGenres': 'Tất cả thể loại',
    'movies:home.allYears': 'Tất cả các năm',
    'movies:home.sort.titleAsc': 'Tiêu đề A–Z',
    'movies:home.sort.titleDesc': 'Tiêu đề Z–A',
    'movies:home.sort.yearDesc': 'Mới nhất',
    'movies:home.sort.yearAsc': 'Cũ nhất',
    'movies:home.moviesByGenre': 'Phim theo Thể loại',
    'movies:home.noMoviesFound': 'Không tìm thấy phim',
    'movies:home.noMoviesDesc': 'Hãy thử thay đổi bộ lọc hoặc từ khóa tìm kiếm để khám phá thêm phim.',
    'movies:home.resetFilters': 'Xóa bộ lọc',
    'movies:continueWatching.title': 'Tiếp tục xem',
    'movies:continueWatching.resume': 'Tiếp tục',
    'movies:continueWatching.progress': '▶ {{time}} · {{percent}}%',
    'recommendation:title': 'Gợi ý cho bạn',
    'recommendation:match': '{{percent}}% phù hợp',
    'recommendation:new_for_you': 'Phim mới cho bạn',
  },
};

function mockTranslate(key: string, optionsOrDefault?: string | Record<string, unknown>, maybeOptions?: Record<string, unknown>): string {
  let defaultValue: string | undefined;
  let options: Record<string, unknown> | undefined;

  if (typeof optionsOrDefault === 'string') {
    defaultValue = optionsOrDefault;
    options = maybeOptions;
  } else if (typeof optionsOrDefault === 'object') {
    options = optionsOrDefault;
    defaultValue = (optionsOrDefault as Record<string, unknown>).defaultValue as string | undefined;
  }

  const langMap = translations[mockLanguage] ?? translations.en;
  let str = langMap[key] ?? defaultValue ?? key;

  if (options) {
    for (const k in options) {
      if (k === 'defaultValue') continue;
      str = str.replace(`{{${k}}}`, String(options[k]));
    }
  }
  return str;
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockTranslate,
    i18n: {
      get language() { return mockLanguage; },
      changeLanguage: (lang: string) => { mockLanguage = lang; return Promise.resolve(); },
    },
  }),
}));

// ── Mock hooks & services ──────────────────────────────────────────────

const heroMovie: MovieListItem = {
  id: 'hero-1',
  title: 'Quiet Morning Lake',
  title_vi: 'Hồ nước buổi sớm yên bình',
  poster_url: '/posters/hero-1.jpg',
  backdrop_url: '/backdrops/hero-1.jpg',
  release_year: 2024,
  genres: ['Drama'],
};

const heroMovieNoVi: MovieListItem = {
  id: 'hero-2',
  title: 'Sunset Valley',
  title_vi: null,
  poster_url: '/posters/hero-2.jpg',
  backdrop_url: '/backdrops/hero-2.jpg',
  release_year: 2023,
  genres: ['Drama'],
};

const heroMovieBlankVi: MovieListItem = {
  id: 'hero-3',
  title: 'Mountain Pass',
  title_vi: '   ',
  poster_url: '/posters/hero-3.jpg',
  backdrop_url: '/backdrops/hero-3.jpg',
  release_year: 2022,
  genres: ['Adventure'],
};

let mockMovies: MovieListItem[] = [heroMovie];

vi.mock('../hooks/useMovies', () => ({
  useMovies: () => ({
    movies: mockMovies,
    loading: false,
    error: null,
  }),
}));

vi.mock('../hooks/useFavorites', () => ({
  useFavorites: () => ({
    isFavorite: () => false,
    toggleFavorite: vi.fn(),
  }),
}));

vi.mock('../hooks/useAuthHook', () => ({
  useAuth: () => ({
    user: null,
  }),
}));

vi.mock('../services/continueWatchingService', () => ({
  getWatchHistory: vi.fn().mockResolvedValue([]),
  getGuestWatchHistory: () => [],
  isWatchCompleted: () => false,
  GUEST_HISTORY_EVENT: 'guest-watch-history-updated',
  formatPlaybackTime: (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  },
}));

vi.mock('../services/recommendationService', () => ({
  getRecommendations: vi.fn().mockResolvedValue([]),
}));

// ── Import component AFTER mocks ───────────────────────────────────────

import HomePage from './HomePage';

function renderHomePage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

/** Get the hero banner title element specifically (by .hero-title class). */
function getHeroTitle(): HTMLElement {
  const el = document.querySelector('.hero-title');
  if (!el) throw new Error('Hero title element (.hero-title) not found');
  return el as HTMLElement;
}

// ── Tests ──────────────────────────────────────────────────────────────

describe('HomePage — Hero Banner i18n', () => {
  beforeEach(() => {
    mockLanguage = 'en';
    mockMovies = [heroMovie];
  });

  // ── Title localization ──

  it('English mode displays the canonical English featured title', () => {
    renderHomePage();
    expect(getHeroTitle()).toHaveTextContent('Quiet Morning Lake');
  });

  it('Vietnamese mode displays title_vi when available', () => {
    mockLanguage = 'vi';
    renderHomePage();
    expect(getHeroTitle()).toHaveTextContent('Hồ nước buổi sớm yên bình');
  });

  it('Vietnamese mode falls back to English title when title_vi is missing', () => {
    mockLanguage = 'vi';
    mockMovies = [heroMovieNoVi];
    renderHomePage();
    expect(getHeroTitle()).toHaveTextContent('Sunset Valley');
  });

  it('blank title_vi falls back to English title', () => {
    mockLanguage = 'vi';
    mockMovies = [heroMovieBlankVi];
    renderHomePage();
    expect(getHeroTitle()).toHaveTextContent('Mountain Pass');
  });

  it('English mode ignores an available title_vi', () => {
    mockLanguage = 'en';
    renderHomePage();
    const heading = getHeroTitle();
    expect(heading).toHaveTextContent('Quiet Morning Lake');
    expect(heading).not.toHaveTextContent('Hồ nước buổi sớm yên bình');
  });

  // ── Button labels ──

  it('English mode displays Watch Now', () => {
    renderHomePage();
    expect(screen.getByText('Watch Now')).toBeTruthy();
  });

  it('English mode displays More Info', () => {
    renderHomePage();
    expect(screen.getByText('More Info')).toBeTruthy();
  });

  it('Vietnamese mode displays Xem ngay', () => {
    mockLanguage = 'vi';
    renderHomePage();
    expect(screen.getByText('Xem ngay')).toBeTruthy();
  });

  it('Vietnamese mode displays Xem thông tin', () => {
    mockLanguage = 'vi';
    renderHomePage();
    expect(screen.getByText('Xem thông tin')).toBeTruthy();
  });

  // ── Language switching behavior ──

  it('changing language updates the banner without reloading', () => {
    const { rerender } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(getHeroTitle()).toHaveTextContent('Quiet Morning Lake');
    expect(screen.getByText('Watch Now')).toBeTruthy();

    // Switch to Vietnamese
    mockLanguage = 'vi';
    rerender(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(getHeroTitle()).toHaveTextContent('Hồ nước buổi sớm yên bình');
    expect(screen.getByText('Xem ngay')).toBeTruthy();
    expect(screen.getByText('Xem thông tin')).toBeTruthy();
  });

  it('changing language does not select another featured movie', () => {
    renderHomePage();
    const watchLink = screen.getByText('Watch Now').closest('a');
    expect(watchLink?.getAttribute('href')).toBe('/movie/hero-1');

    mockLanguage = 'vi';
    renderHomePage();
    const watchLinkVi = screen.getByText('Xem ngay').closest('a');
    expect(watchLinkVi?.getAttribute('href')).toBe('/movie/hero-1');
  });

  it('changing language does not refetch recommendations solely for banner translation', async () => {
    const { getRecommendations: mockGetRecs } = await import('../services/recommendationService') as { getRecommendations: ReturnType<typeof vi.fn> };
    mockGetRecs.mockClear();

    const { rerender } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    const callsAfterMount = mockGetRecs.mock.calls.length;

    // Switch language
    mockLanguage = 'vi';
    rerender(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    // No additional recommendation calls
    expect(mockGetRecs.mock.calls.length).toBe(callsAfterMount);
  });

  // ── Navigation behavior ──

  it('Watch button still opens the correct movie', () => {
    renderHomePage();
    const link = screen.getByText('Watch Now').closest('a');
    expect(link?.getAttribute('href')).toBe('/movie/hero-1');
  });

  it('More Info still opens the correct movie detail', () => {
    renderHomePage();
    const link = screen.getByText('More Info').closest('a');
    expect(link?.getAttribute('href')).toBe('/movie/hero-1');
  });

  // ── Accessibility ──

  it('Watch Now link has localized aria-label with movie title', () => {
    renderHomePage();
    const link = screen.getByLabelText('Watch Quiet Morning Lake');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/movie/hero-1');
  });

  it('More Info link has localized aria-label with movie title', () => {
    renderHomePage();
    const link = screen.getByLabelText('More info about Quiet Morning Lake');
    expect(link).toBeTruthy();
  });

  it('Vietnamese aria-labels use localized movie title', () => {
    mockLanguage = 'vi';
    renderHomePage();
    expect(screen.getByLabelText('Xem Hồ nước buổi sớm yên bình')).toBeTruthy();
    expect(screen.getByLabelText('Xem thông tin về Hồ nước buổi sớm yên bình')).toBeTruthy();
  });

  it('backdrop has accessible img role with localized alt text', () => {
    renderHomePage();
    const backdrop = screen.getByRole('img', { name: /Quiet Morning Lake featured backdrop/ });
    expect(backdrop).toBeTruthy();
  });

  it('Vietnamese backdrop alt text uses localized title', () => {
    mockLanguage = 'vi';
    renderHomePage();
    const backdrop = screen.getByRole('img', { name: /Ảnh nền phim Hồ nước buổi sớm yên bình/ });
    expect(backdrop).toBeTruthy();
  });

  // ── Theme not affected ──

  it('theme selection remains unchanged', () => {
    // Theme state is managed by ThemeProvider, not by HomePage.
    // Rendering HomePage doesn't interfere with data-theme.
    const initialTheme = document.documentElement.dataset.theme;
    renderHomePage();
    expect(document.documentElement.dataset.theme).toBe(initialTheme);
  });
});

