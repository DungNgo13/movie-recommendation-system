import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import MovieForm from './MovieForm';
import type { Movie } from '../../models';
import type { MovieSourceStatus } from '../../services/movieSourceService';

const uploadMovieVideoMock = vi.fn();
const processMovieVideoMock = vi.fn();
vi.mock('../../services/movieService', () => ({
  uploadMovieVideo: (...args: unknown[]) => uploadMovieVideoMock(...args),
  processMovieVideo: (...args: unknown[]) => processMovieVideoMock(...args),
  uploadMovieImage: vi.fn(),
  getMovieProcessingStatus: vi.fn(),
  getMovieById: vi.fn(),
}));

// Server-side source state; tests mutate `serverSource` to simulate the DB.
let serverSource: MovieSourceStatus;
const getMovieSourceStatusMock = vi.fn();
vi.mock('../../services/movieSourceService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/movieSourceService')>();
  return {
    ...actual,
    getMovieSourceStatus: (id: string) => getMovieSourceStatusMock(id),
  };
});

function sourceStatus(overrides: Partial<MovieSourceStatus> = {}): MovieSourceStatus {
  return {
    movie_id: 'movie-1',
    source_storage: 'local',
    source_available: true,
    processing_status: 'uploaded',
    hls_ready: false,
    hls_processing_supported: true,
    ...overrides,
  };
}
const R2_SOURCE = { source_storage: 'r2' as const, hls_processing_supported: false };

// Replace the R2 control with a stub that exposes its callbacks, so these
// tests focus on how MovieForm reacts (R2 flow itself: R2DirectUpload.test.tsx).
interface StubProps {
  movieId: string;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onCompleted?: (movie: Movie | null) => void;
}
let lastStubProps: StubProps | null = null;
vi.mock('./R2DirectUpload', () => ({
  default: (props: StubProps) => {
    lastStubProps = props;
    return <div data-testid="r2-stub" data-movie-id={props.movieId} data-disabled={String(!!props.disabled)} />;
  },
}));

function makeMovie(overrides: Partial<Movie> = {}): Movie {
  return {
    id: 'movie-1',
    title: 'Inception',
    overview: 'A thief',
    release_date: '2010-01-01',
    genres: ['Action'],
    cast: ['Leo'],
    keywords: ['dream'],
    director: 'Nolan',
    poster_url: null,
    backdrop_url: null,
    video_status: 'uploaded',
    ...overrides,
  } as Movie;
}

const startEncodingButton = () => screen.queryByRole('button', { name: 'admin:movieForm.startEncoding' });
const storage = () => screen.getByTestId('source-storage').getAttribute('data-storage');

function renderForm(movie: Movie | null = makeMovie()) {
  return render(<MovieForm movie={movie} onSubmit={vi.fn()} onCancel={vi.fn()} />);
}

beforeEach(() => {
  uploadMovieVideoMock.mockReset();
  processMovieVideoMock.mockReset();
  lastStubProps = null;
  serverSource = sourceStatus();
  getMovieSourceStatusMock.mockReset().mockImplementation(async () => serverSource);
});

describe('MovieForm video section', () => {
  it('renders both the local fallback upload and the R2 direct upload for an existing movie', async () => {
    renderForm();
    expect(screen.getByLabelText('admin:r2Upload.localFallbackLabel')).toBeInTheDocument();
    expect(screen.getByTestId('r2-stub')).toHaveAttribute('data-movie-id', 'movie-1');
    await waitFor(() => expect(storage()).toBe('local'));
  });

  it('does not render upload controls or load source status before the movie exists', () => {
    renderForm(null);
    expect(screen.queryByTestId('r2-stub')).not.toBeInTheDocument();
    expect(screen.getByText('admin:movieForm.createFirst')).toBeInTheDocument();
    expect(getMovieSourceStatusMock).not.toHaveBeenCalled();
  });

  it('local upload fallback still uses the multipart server upload', async () => {
    uploadMovieVideoMock.mockImplementation(async (_id: string, _file: File, onProgress: (p: number) => void) => {
      onProgress(50);
      return makeMovie({ video_status: 'uploaded', video_url: '/media/videos/source/x.mp4' });
    });
    renderForm(makeMovie({ video_status: 'pending' }));

    const file = new File([new Uint8Array(4)], 'local.mp4', { type: 'video/mp4' });
    fireEvent.change(screen.getByLabelText('admin:r2Upload.localFallbackLabel'), { target: { files: [file] } });

    await waitFor(() => expect(uploadMovieVideoMock).toHaveBeenCalledWith('movie-1', file, expect.any(Function)));
    await waitFor(() => expect(startEncodingButton()).toBeInTheDocument());
  });

  it('disables the local upload while an R2 upload is busy', async () => {
    renderForm();
    await waitFor(() => expect(storage()).toBe('local'));
    const local = screen.getByLabelText('admin:r2Upload.localFallbackLabel');
    expect(local).not.toBeDisabled();
    act(() => lastStubProps?.onBusyChange?.(true));
    expect(local).toBeDisabled();
    expect(startEncodingButton()).toBeDisabled();
    act(() => lastStubProps?.onBusyChange?.(false));
    expect(local).not.toBeDisabled();
  });

  it('does not trigger HLS processing after R2 completion and hides local encode', async () => {
    renderForm(makeMovie({ video_status: 'uploaded' }));
    await waitFor(() => expect(startEncodingButton()).toBeInTheDocument());

    serverSource = sourceStatus(R2_SOURCE); // backend now reports the R2 source
    act(() => lastStubProps?.onCompleted?.(makeMovie({ video_status: 'uploaded' })));

    expect(startEncodingButton()).not.toBeInTheDocument(); // optimistic
    await waitFor(() => expect(getMovieSourceStatusMock).toHaveBeenCalledTimes(2)); // re-sync
    expect(storage()).toBe('r2');
    expect(startEncodingButton()).not.toBeInTheDocument();
    expect(processMovieVideoMock).not.toHaveBeenCalled();
  });

  it('a later local upload restores the local encode action', async () => {
    serverSource = sourceStatus(R2_SOURCE);
    uploadMovieVideoMock.mockImplementation(async () => {
      serverSource = sourceStatus(); // backend switches back to local
      return makeMovie({ video_status: 'uploaded' });
    });
    renderForm(makeMovie({ video_status: 'uploaded' }));
    await waitFor(() => expect(storage()).toBe('r2'));
    expect(startEncodingButton()).not.toBeInTheDocument();

    const file = new File([new Uint8Array(4)], 'local.mp4', { type: 'video/mp4' });
    fireEvent.change(screen.getByLabelText('admin:r2Upload.localFallbackLabel'), { target: { files: [file] } });
    await waitFor(() => expect(startEncodingButton()).toBeInTheDocument());
    expect(storage()).toBe('local');
  });
});

describe('MovieForm source storage persistence', () => {
  it('after a page refresh, an R2-backed movie is recognised from the server and encode stays blocked', async () => {
    serverSource = sourceStatus({ ...R2_SOURCE, processing_status: 'uploaded' });
    // Fresh mount == page refresh: no in-memory upload state exists.
    renderForm(makeMovie({ video_status: 'uploaded' }));

    await waitFor(() => expect(storage()).toBe('r2'));
    expect(getMovieSourceStatusMock).toHaveBeenCalledWith('movie-1');
    expect(screen.getByText('admin:sourceStatus.r2')).toBeInTheDocument();
    expect(screen.getByText('admin:sourceStatus.available')).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('admin:sourceStatus.hlsUnsupported');
    expect(startEncodingButton()).not.toBeInTheDocument();
  });

  it('shows an unavailable R2 source (no verified upload) and still blocks encode', async () => {
    serverSource = sourceStatus({ ...R2_SOURCE, source_available: false });
    renderForm();
    await waitFor(() => expect(storage()).toBe('r2'));
    expect(screen.getByText('admin:sourceStatus.unavailable')).toBeInTheDocument();
    expect(startEncodingButton()).not.toBeInTheDocument();
  });

  it('allows encoding for R2 source when hls_processing_supported is true (Phase 3)', async () => {
    serverSource = sourceStatus({ source_storage: 'r2', source_available: true, hls_processing_supported: true, processing_status: 'uploaded' });
    renderForm(makeMovie({ video_status: 'uploaded' }));

    await waitFor(() => expect(storage()).toBe('r2'));
    expect(screen.getByText('admin:sourceStatus.r2')).toBeInTheDocument();
    expect(screen.getByText('admin:sourceStatus.available')).toBeInTheDocument();
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
    expect(startEncodingButton()).toBeInTheDocument();
  });

  it('keeps encode available for local sources', async () => {
    renderForm();
    await waitFor(() => expect(storage()).toBe('local'));
    expect(screen.getByText('admin:sourceStatus.local')).toBeInTheDocument();
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
    expect(startEncodingButton()).toBeInTheDocument();
  });

  it('shows a load error without blocking the form (backend still guards encoding)', async () => {
    getMovieSourceStatusMock.mockRejectedValue(new Error('boom'));
    renderForm();
    await waitFor(() => expect(screen.getByText('admin:sourceStatus.loadFailed')).toBeInTheDocument());
    expect(startEncodingButton()).toBeInTheDocument();
  });

  it('handles the backend R2 guard (409 hls_r2_source_unsupported) and re-syncs status', async () => {
    renderForm(); // stale view: local
    await waitFor(() => expect(startEncodingButton()).toBeInTheDocument());

    serverSource = sourceStatus(R2_SOURCE); // changed elsewhere (e.g. another tab)
    processMovieVideoMock.mockRejectedValue(
      Object.assign(new Error('The active source video is stored in R2.'), {
        status: 409, code: 'hls_r2_source_unsupported',
      }),
    );
    fireEvent.click(startEncodingButton()!);

    await waitFor(() => expect(storage()).toBe('r2'));
    expect(screen.getByText('admin:sourceStatus.hlsUnsupported', { selector: '.admin-form-error' })).toBeInTheDocument();
    expect(startEncodingButton()).not.toBeInTheDocument();
  });
});
