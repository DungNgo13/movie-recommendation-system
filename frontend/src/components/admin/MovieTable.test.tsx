import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import MovieTable from './MovieTable';
import type { Movie } from '../../models';

// ─── i18n mock ───────────────────────────────────────────────────────────────
// Simulate i18next key resolution for the admin namespace.
// Keys used by MovieTable that lack an inline fallback string are listed here.
const i18nMap: Record<string, string> = {
  'admin:movieTable.quality': 'Quality',
  'admin:movieTable.dataQuality': 'Data Quality',
  'admin:movieTable.dataQualityTooltip': 'Data completeness score for the AI recommendation engine (0–100). Hover each row for missing fields.',
  'admin:movieTable.videoStatus': 'Video Status',
  'admin:movieTable.optimised': 'Optimised',
  'admin:movieTable.average': 'Average',
  'admin:movieTable.critical': 'Critical',
  'admin:movieTable.allFieldsComplete': 'All AI fields complete — engine fully optimised',
  'admin:movieTable.missing': 'Missing:',
  'admin:movieTable.missingGenres': 'Genres (+30)',
  'admin:movieTable.missingCast': 'Cast (+20)',
  'admin:movieTable.missingOverview': 'Overview >50 chars (+20)',
  'admin:movieTable.missingDirector': 'Director (+15)',
  'admin:movieTable.missingPosterBackdrop': 'Poster & Backdrop (+10)',
  'admin:movieTable.play': 'Play',
  'admin:movieTable.stop': 'Stop',
  'admin:movieTable.cancelling': 'Cancelling…',
  'admin:movieTable.processing': 'Processing',
  'admin:movieTable.reEncode': 'Re-encode',
  'admin:movieTable.encode': 'Encode',
  'admin:movieTable.encoding': 'Encoding…',
  'admin:movieTable.pending': 'Pending',
  'admin:movieTable.stopTooltip': 'Stop encoding',
  'admin:movieTable.reEncodeTooltip': 'Re-encode (replace existing HLS)',
  'admin:movieTable.startEncodeTooltip': 'Start multi-quality HLS encoding',
  'admin:movieTable.videoStatusReady': 'Ready',
  'admin:movieTable.videoStatusProcessing': 'Processing',
  'admin:movieTable.videoStatusFailed': 'Failed',
  'admin:movieTable.videoStatusUploaded': 'Uploaded',
  'admin:movieTable.videoStatusNoVideo': 'No video',
};

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => i18nMap[key] ?? fallback ?? key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));


// ─── Factory ─────────────────────────────────────────────────────────────────
function makeMovie(overrides: Partial<Movie> = {}): Movie {
  return {
    id: 'movie-1',
    title: 'Inception',
    overview: 'A thief who steals corporate secrets',
    release_date: '2010-07-16',
    genres: ['Action', 'Sci-Fi'],
    cast: ['Leonardo DiCaprio'],
    keywords: ['heist', 'dream'],
    director: 'Christopher Nolan',
    poster_url: '/media/images/posters/inception.jpg',
    backdrop_url: '/media/images/backdrops/inception.jpg',
    ...overrides,
  };
}

const noop = vi.fn();
const noopAsync = vi.fn(async () => {});

function renderTable(movies: Movie[] = [makeMovie()]) {
  return render(
    <MovieTable
      movies={movies}
      onEdit={noop}
      onDelete={noop}
      onCancelEncode={noopAsync}
      onStartEncode={noopAsync}
    />
  );
}

beforeEach(() => {
  noop.mockClear();
  noopAsync.mockClear();
});

// ─── Semantic structure ──────────────────────────────────────────────────────

describe('MovieTable — semantic DOM structure', () => {
  it('renders each movie as a semantic <tr>', () => {
    const { container } = renderTable([makeMovie(), makeMovie({ id: 'movie-2', title: 'Movie 2' })]);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2);
  });

  it('renders data items inside semantic <td> elements', () => {
    const { container } = renderTable();
    const cells = container.querySelectorAll('tbody tr td');
    // 7 columns: title, director, year, quality, data quality, video status, actions
    expect(cells.length).toBe(7);
  });

  it('actions cell has className admin-table-actions', () => {
    const { container } = renderTable();
    const actionsCell = container.querySelector('td.admin-table-actions');
    expect(actionsCell).toBeTruthy();
  });
});

// ─── Inner wrapper structure ─────────────────────────────────────────────────

describe('MovieTable — actions inner wrapper', () => {
  it('actions cell contains .admin-table-actions__inner wrapper', () => {
    const { container } = renderTable();
    const inner = container.querySelector('td.admin-table-actions .admin-table-actions__inner');
    expect(inner).toBeTruthy();
  });

  it('Edit and Delete buttons are inside the inner wrapper', () => {
    const { container } = renderTable();
    const inner = container.querySelector('.admin-table-actions__inner')!;
    const buttons = inner.querySelectorAll('button');
    expect(buttons.length).toBe(2);
    expect(buttons[0].textContent).toMatch(/edit/i);
    expect(buttons[1].textContent).toMatch(/delete/i);
  });

  it('actions cell itself does not receive a flex-specific inline style', () => {
    const { container } = renderTable();
    const actionsCell = container.querySelector('td.admin-table-actions') as HTMLElement;
    const inlineStyle = actionsCell.getAttribute('style') || '';
    expect(inlineStyle).not.toContain('display');
    expect(inlineStyle).not.toContain('flex');
  });

  it('both buttons use type="button"', () => {
    const { container } = renderTable();
    const buttons = container.querySelectorAll('.admin-table-actions__inner button');
    buttons.forEach(btn => {
      expect(btn.getAttribute('type')).toBe('button');
    });
  });
});

// ─── Callbacks ───────────────────────────────────────────────────────────────

describe('MovieTable — action callbacks', () => {
  it('Edit button calls onEdit with the correct movie', () => {
    const movie = makeMovie({ id: 'abc-123', title: 'Test Movie' });
    renderTable([movie]);
    const editBtn = screen.getByText(/edit/i);
    fireEvent.click(editBtn);
    expect(noop).toHaveBeenCalledWith(movie);
  });

  it('Delete button calls onDelete with the correct movie', () => {
    const movie = makeMovie({ id: 'xyz-456', title: 'Another Movie' });
    renderTable([movie]);
    const deleteBtn = screen.getByText(/delete/i);
    fireEvent.click(deleteBtn);
    expect(noop).toHaveBeenCalledWith(movie);
  });
});

// ─── Content rendering ──────────────────────────────────────────────────────

describe('MovieTable — content rendering', () => {
  it('renders Vietnamese title fallback when no title_vi', () => {
    renderTable([makeMovie({ title_vi: undefined })]);
    expect(screen.getByText(/no vietnamese title/i)).toBeTruthy();
  });

  it('renders Vietnamese title when present', () => {
    renderTable([makeMovie({ title_vi: 'Khởi Đầu' })]);
    expect(screen.getByText('Khởi Đầu')).toBeTruthy();
  });

  it('renders quality badges when available_qualities is set', () => {
    renderTable([makeMovie({ available_qualities: '360p,720p,1080p' })]);
    expect(screen.getByText('360p')).toBeTruthy();
    expect(screen.getByText('720p')).toBeTruthy();
    expect(screen.getByText('1080p')).toBeTruthy();
  });

  it('renders video status', () => {
    renderTable([makeMovie({ video_status: 'ready' })]);
    expect(screen.getByText('Ready')).toBeTruthy();
  });

  it('renders Encode button for uploaded status', () => {
    renderTable([makeMovie({ video_status: 'uploaded' })]);
    expect(screen.getByText('Encode')).toBeTruthy();
  });

  it('renders Re-encode button for ready status', () => {
    renderTable([makeMovie({ video_status: 'ready' })]);
    expect(screen.getByText('Re-encode')).toBeTruthy();
  });
});

// ─── Multiple rows ──────────────────────────────────────────────────────────

describe('MovieTable — multiple movies', () => {
  it('renders the correct number of rows for multiple movies', () => {
    const movies = [
      makeMovie({ id: '1', title: 'Movie A' }),
      makeMovie({ id: '2', title: 'Movie B' }),
      makeMovie({ id: '3', title: 'Movie C' }),
    ];
    const { container } = renderTable(movies);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);
  });

  it('each row has its own inner wrapper', () => {
    const movies = [
      makeMovie({ id: '1', title: 'Movie A' }),
      makeMovie({ id: '2', title: 'Movie B' }),
    ];
    const { container } = renderTable(movies);
    const inners = container.querySelectorAll('.admin-table-actions__inner');
    expect(inners.length).toBe(2);
  });

  it('action buttons do not wrap into separate DOM rows', () => {
    const { container } = renderTable();
    const inner = container.querySelector('.admin-table-actions__inner')!;
    const buttons = inner.querySelectorAll('button');
    // Both buttons should be direct children of the inner wrapper, not in separate divs/rows
    expect(buttons.length).toBe(2);
    for (const btn of buttons) {
      expect(btn.parentElement).toBe(inner);
    }
  });
});
