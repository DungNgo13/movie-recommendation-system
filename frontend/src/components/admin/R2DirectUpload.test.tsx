import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import R2DirectUpload from './R2DirectUpload';
import { FakeXHR } from '../../test/fakeXhr';

vi.mock('../../services/authService', () => ({ getToken: () => 'admin-token' }));

const getMovieByIdMock = vi.fn();
vi.mock('../../services/movieService', () => ({
  getMovieById: (id: string) => getMovieByIdMock(id),
}));

const MOVIE_ID = 'movie-123';
const SESSION_ID = 'session-456';
const FAKE_PUT_URL = 'https://r2.test.invalid/signed-put-capability';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const session = {
  id: SESSION_ID, movie_id: MOVIE_ID, status: 'pending', original_filename: 'clip.mp4',
  content_type: 'video/mp4', expected_size: 1000, actual_size: null, error: null,
  created_at: '2026-10-25T00:00:00Z', expires_at: '2026-10-25T00:15:00Z', completed_at: null,
};

const presignOk = () => jsonResponse(201, {
  session,
  upload_url: FAKE_PUT_URL,
  upload_method: 'PUT',
  upload_headers: { 'Content-Type': 'video/mp4' },
  expires_in_seconds: 900,
});
const completeOk = () => jsonResponse(200, { ...session, status: 'completed', actual_size: 1000 });

type Handler = () => Response | Promise<Response>;

let presignHandler: Handler;
let completeHandlers: Handler[];
let fetchMock: ReturnType<typeof vi.fn>;

function calls(pathSuffix: string): number {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith(pathSuffix)).length;
}

function makeFile(name = 'clip.mp4', type = 'video/mp4', size = 1000): File {
  return new File([new Uint8Array(size)], name, { type });
}

function selectFile(file: File) {
  const input = screen.getByLabelText('admin:r2Upload.selectFile') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

const status = () => screen.getByTestId('r2-upload-status').textContent;
const phase = () => screen.getByTestId('r2-direct-upload').getAttribute('data-phase');

beforeEach(() => {
  FakeXHR.reset();
  vi.stubGlobal('XMLHttpRequest', FakeXHR);
  presignHandler = presignOk;
  completeHandlers = [completeOk];
  getMovieByIdMock.mockReset().mockResolvedValue({ id: MOVIE_ID, title: 'M', video_status: 'pending' });
  fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith(`/admin/movies/${MOVIE_ID}/uploads`)) return presignHandler();
    if (url.endsWith(`/uploads/${SESSION_ID}/complete`)) {
      const next = completeHandlers.length > 1 ? completeHandlers.shift()! : completeHandlers[0];
      return next();
    }
    throw new Error(`Unexpected fetch ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function startAndReachUploading() {
  selectFile(makeFile());
  await waitFor(() => expect(phase()).toBe('uploading'));
  return FakeXHR.last();
}

describe('R2DirectUpload', () => {
  it('starts idle with no progress bar', () => {
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    expect(phase()).toBe('idle');
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('runs requesting_url → uploading → verifying → completed with real progress', async () => {
    const onCompleted = vi.fn();
    const seen: string[] = [];
    render(<R2DirectUpload movieId={MOVIE_ID} onCompleted={onCompleted} />);

    let releaseComplete: (r: Response) => void = () => {};
    completeHandlers = [() => new Promise<Response>((resolve) => { releaseComplete = resolve; })];

    selectFile(makeFile());
    seen.push(phase()!);
    expect(status()).toBe('admin:r2Upload.status.requestingUrl');

    await waitFor(() => expect(phase()).toBe('uploading'));
    seen.push(phase()!);
    const xhr = FakeXHR.last();
    expect(xhr.method).toBe('PUT');
    expect(xhr.requestHeaders).toEqual({ 'Content-Type': 'video/mp4' });

    act(() => xhr.progress(250, 1000));
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '25');

    // All bytes sent, but backend has not confirmed → must not show 100%.
    act(() => xhr.progress(1000, 1000));
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '99');

    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('verifying'));
    seen.push(phase()!);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '99');
    expect(status()).toBe('admin:r2Upload.status.verifying');

    await act(async () => releaseComplete(completeOk()));
    await waitFor(() => expect(phase()).toBe('completed'));
    seen.push(phase()!);

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
    expect(seen).toEqual(['requesting_url', 'uploading', 'verifying', 'completed']);
    expect(getMovieByIdMock).toHaveBeenCalledWith(MOVIE_ID);
    expect(onCompleted).toHaveBeenCalledWith(expect.objectContaining({ id: MOVIE_ID }));
    expect(screen.getByText('admin:r2Upload.hlsNotAvailable')).toBeInTheDocument();
  });

  it('never renders the presigned URL', async () => {
    const { container } = render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    expect(container.innerHTML).not.toContain('signed-put-capability');
    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('completed'));
    expect(container.innerHTML).not.toContain('signed-put-capability');
  });

  it('rejects an invalid file type without calling the API', () => {
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    selectFile(makeFile('poster.png', 'image/png'));
    expect(phase()).toBe('failed');
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.invalid_type');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('rejects an oversize file without calling the API', () => {
    render(<R2DirectUpload movieId={MOVIE_ID} maxBytes={500} />);
    selectFile(makeFile('big.mp4', 'video/mp4', 501));
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.too_large');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('shows presign failure (movie not found) and does not start a PUT', async () => {
    presignHandler = () => jsonResponse(404, { detail: 'Movie not found' });
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    selectFile(makeFile());
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(status()).toBe('admin:r2Upload.status.uploadFailed');
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.not_found');
    expect(FakeXHR.instances).toHaveLength(0);
  });

  it('calls onUnauthorized on 401 from the presign endpoint', async () => {
    presignHandler = () => jsonResponse(401, { detail: 'Not authenticated' });
    const onUnauthorized = vi.fn();
    render(<R2DirectUpload movieId={MOVIE_ID} onUnauthorized={onUnauthorized} />);
    selectFile(makeFile());
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.unauthorized');
  });

  it('shows forbidden (non-admin) without redirecting', async () => {
    presignHandler = () => jsonResponse(403, { detail: 'Forbidden' });
    const onUnauthorized = vi.fn();
    render(<R2DirectUpload movieId={MOVIE_ID} onUnauthorized={onUnauthorized} />);
    selectFile(makeFile());
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(onUnauthorized).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.forbidden');
  });

  it('PUT failure: does not call completion and offers no verification retry', async () => {
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(500, '<Error/>'));
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(status()).toBe('admin:r2Upload.status.uploadFailed');
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.put_failed');
    expect(calls('/complete')).toBe(0);
    expect(screen.queryByRole('button', { name: 'admin:r2Upload.retryVerify' })).not.toBeInTheDocument();
  });

  it('expired presigned URL during PUT is reported as expired', async () => {
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(403, '<Message>Request has expired</Message>'));
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.expired');
    expect(calls('/complete')).toBe(0);
  });

  it('network interruption during PUT is reported as network failure', async () => {
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.failNetwork());
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.errors.network');
    expect(calls('/complete')).toBe(0);
  });

  it('cancel aborts the XHR and ends in cancelled without completion', async () => {
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.progress(400, 1000));
    fireEvent.click(screen.getByRole('button', { name: 'admin:r2Upload.cancel' }));
    expect(xhr.aborted).toBe(true);
    await waitFor(() => expect(phase()).toBe('cancelled'));
    expect(status()).toBe('admin:r2Upload.status.cancelled');
    expect(calls('/complete')).toBe(0);
    expect(screen.getByLabelText('admin:r2Upload.selectFile')).not.toBeDisabled();
  });

  it('cancel while requesting the URL never starts the PUT', async () => {
    let releasePresign: (r: Response) => void = () => {};
    presignHandler = () => new Promise<Response>((resolve) => { releasePresign = resolve; });
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    selectFile(makeFile());
    fireEvent.click(screen.getByRole('button', { name: 'admin:r2Upload.cancel' }));
    await act(async () => releasePresign(presignOk()));
    await waitFor(() => expect(phase()).toBe('cancelled'));
    expect(FakeXHR.instances).toHaveLength(0);
  });

  it.each([
    [502, 'Could not verify upload with storage.', 'storage_error'],
    [503, 'R2 storage is not configured.', 'unavailable'],
    [409, 'Uploaded object not found. Finish the upload, then retry completion.', 'object_missing'],
  ])('completion %i is retryable without re-uploading the file', async (code, detail, kind) => {
    completeHandlers = [() => jsonResponse(code, { detail }), completeOk];
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(200));

    await waitFor(() => expect(phase()).toBe('failed'));
    expect(status()).toBe('admin:r2Upload.status.verifyFailed');
    expect(screen.getByRole('alert')).toHaveTextContent(`admin:r2Upload.errors.${kind}`);
    // Not 100% — the object is not confirmed.
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'admin:r2Upload.retryVerify' }));
    await waitFor(() => expect(phase()).toBe('completed'));

    expect(FakeXHR.instances).toHaveLength(1);       // exactly one PUT
    expect(calls(`/admin/movies/${MOVIE_ID}/uploads`)).toBe(1); // one presign
    expect(calls('/complete')).toBe(2);              // original + retry
  });

  it('completion network drop is retryable', async () => {
    completeHandlers = [() => Promise.reject(new TypeError('Failed to fetch')), completeOk];
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('failed'));
    fireEvent.click(screen.getByRole('button', { name: 'admin:r2Upload.retryVerify' }));
    await waitFor(() => expect(phase()).toBe('completed'));
    expect(FakeXHR.instances).toHaveLength(1);
  });

  it.each([
    [422, 'Uploaded size 999 bytes does not match declared size 1000 bytes.', 'mismatch'],
    [409, 'Upload session expired', 'expired'],
    [409, 'Upload session is failed', 'conflict'],
  ])('completion %i "%s" requires a new upload (no retry button)', async (code, detail, kind) => {
    completeHandlers = [() => jsonResponse(code, { detail })];
    render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(screen.getByRole('alert')).toHaveTextContent(`admin:r2Upload.errors.${kind}`);
    expect(screen.getByRole('alert')).toHaveTextContent('admin:r2Upload.newUploadRequired');
    expect(screen.queryByRole('button', { name: 'admin:r2Upload.retryVerify' })).not.toBeInTheDocument();
    expect(calls('/complete')).toBe(1);
  });

  it('completion 401 triggers onUnauthorized', async () => {
    completeHandlers = [() => jsonResponse(401, { detail: 'Not authenticated' })];
    const onUnauthorized = vi.fn();
    render(<R2DirectUpload movieId={MOVIE_ID} onUnauthorized={onUnauthorized} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('failed'));
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('still completes when the movie refresh fails', async () => {
    getMovieByIdMock.mockRejectedValue(new Error('Failed to fetch movie'));
    const onCompleted = vi.fn();
    render(<R2DirectUpload movieId={MOVIE_ID} onCompleted={onCompleted} />);
    const xhr = await startAndReachUploading();
    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('completed'));
    expect(onCompleted).toHaveBeenCalledWith(null);
  });

  it('reports busy state to the parent and disables the picker while busy', async () => {
    const onBusyChange = vi.fn();
    render(<R2DirectUpload movieId={MOVIE_ID} onBusyChange={onBusyChange} />);
    const xhr = await startAndReachUploading();
    expect(screen.getByLabelText('admin:r2Upload.selectFile')).toBeDisabled();
    expect(onBusyChange).toHaveBeenLastCalledWith(true);
    act(() => xhr.respond(200));
    await waitFor(() => expect(phase()).toBe('completed'));
    expect(onBusyChange).toHaveBeenLastCalledWith(false);
  });

  it('aborts an in-flight PUT on unmount', async () => {
    const { unmount } = render(<R2DirectUpload movieId={MOVIE_ID} />);
    const xhr = await startAndReachUploading();
    unmount();
    expect(xhr.aborted).toBe(true);
  });
});
