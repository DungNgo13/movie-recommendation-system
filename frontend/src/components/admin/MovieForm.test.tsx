import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import MovieForm from './MovieForm';
import type { Movie } from '../../models';

const uploadMovieVideoMock = vi.fn();
const processMovieVideoMock = vi.fn();
vi.mock('../../services/movieService', () => ({
  uploadMovieVideo: (...args: unknown[]) => uploadMovieVideoMock(...args),
  processMovieVideo: (...args: unknown[]) => processMovieVideoMock(...args),
  uploadMovieImage: vi.fn(),
  getMovieProcessingStatus: vi.fn(),
  getMovieById: vi.fn(),
}));

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

beforeEach(() => {
  uploadMovieVideoMock.mockReset();
  processMovieVideoMock.mockReset();
  lastStubProps = null;
});

describe('MovieForm video section', () => {
  it('renders both the local fallback upload and the R2 direct upload for an existing movie', () => {
    render(<MovieForm movie={makeMovie()} onSubmit={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByLabelText('admin:r2Upload.localFallbackLabel')).toBeInTheDocument();
    expect(screen.getByTestId('r2-stub')).toHaveAttribute('data-movie-id', 'movie-1');
  });

  it('does not render upload controls before the movie exists', () => {
    render(<MovieForm movie={null} onSubmit={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.queryByTestId('r2-stub')).not.toBeInTheDocument();
    expect(screen.getByText('admin:movieForm.createFirst')).toBeInTheDocument();
  });

  it('local upload fallback still uses the multipart server upload', async () => {
    uploadMovieVideoMock.mockImplementation(async (_id: string, _file: File, onProgress: (p: number) => void) => {
      onProgress(50);
      return makeMovie({ video_status: 'uploaded', video_url: '/media/videos/source/x.mp4' });
    });
    render(<MovieForm movie={makeMovie({ video_status: 'pending' })} onSubmit={vi.fn()} onCancel={vi.fn()} />);

    const file = new File([new Uint8Array(4)], 'local.mp4', { type: 'video/mp4' });
    fireEvent.change(screen.getByLabelText('admin:r2Upload.localFallbackLabel'), { target: { files: [file] } });

    await waitFor(() => expect(uploadMovieVideoMock).toHaveBeenCalledWith('movie-1', file, expect.any(Function)));
    await waitFor(() => expect(startEncodingButton()).toBeInTheDocument());
  });

  it('disables the local upload while an R2 upload is busy', () => {
    render(<MovieForm movie={makeMovie()} onSubmit={vi.fn()} onCancel={vi.fn()} />);
    const local = screen.getByLabelText('admin:r2Upload.localFallbackLabel');
    expect(local).not.toBeDisabled();
    act(() => lastStubProps?.onBusyChange?.(true));
    expect(local).toBeDisabled();
    expect(startEncodingButton()).toBeDisabled();
    act(() => lastStubProps?.onBusyChange?.(false));
    expect(local).not.toBeDisabled();
  });

  it('does not trigger HLS processing after R2 completion and hides local encode', () => {
    render(<MovieForm movie={makeMovie({ video_status: 'uploaded' })} onSubmit={vi.fn()} onCancel={vi.fn()} />);
    expect(startEncodingButton()).toBeInTheDocument();

    act(() => lastStubProps?.onCompleted?.(makeMovie({ video_status: 'uploaded' })));

    expect(processMovieVideoMock).not.toHaveBeenCalled();
    expect(startEncodingButton()).not.toBeInTheDocument();
  });

  it('a later local upload restores the local encode action', async () => {
    uploadMovieVideoMock.mockResolvedValue(makeMovie({ video_status: 'uploaded' }));
    render(<MovieForm movie={makeMovie({ video_status: 'uploaded' })} onSubmit={vi.fn()} onCancel={vi.fn()} />);
    act(() => lastStubProps?.onCompleted?.(null));
    expect(startEncodingButton()).not.toBeInTheDocument();

    const file = new File([new Uint8Array(4)], 'local.mp4', { type: 'video/mp4' });
    fireEvent.change(screen.getByLabelText('admin:r2Upload.localFallbackLabel'), { target: { files: [file] } });
    await waitFor(() => expect(startEncodingButton()).toBeInTheDocument());
  });
});
