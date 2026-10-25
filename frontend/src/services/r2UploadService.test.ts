import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FakeXHR } from '../test/fakeXhr';
import {
  R2UploadError,
  completeR2UploadSession,
  createR2UploadSession,
  putFileToR2,
  resolveVideoContentType,
  validateR2VideoFile,
} from './r2UploadService';

vi.mock('./authService', () => ({ getToken: () => 'test-token' }));

const API = 'http://localhost:8000/api/v1';
const MOVIE_ID = '11111111-1111-1111-1111-111111111111';
const SESSION_ID = '22222222-2222-2222-2222-222222222222';
const FAKE_PUT_URL = 'https://r2.test.invalid/presigned-put';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeSession(overrides: Record<string, unknown> = {}) {
  return {
    id: SESSION_ID,
    movie_id: MOVIE_ID,
    status: 'pending',
    original_filename: 'clip.mp4',
    content_type: 'video/mp4',
    expected_size: 10,
    actual_size: null,
    error: null,
    created_at: '2026-10-25T00:00:00Z',
    expires_at: '2026-10-25T00:15:00Z',
    completed_at: null,
    ...overrides,
  };
}

async function captureError(promise: Promise<unknown>): Promise<R2UploadError> {
  try {
    await promise;
  } catch (err) {
    if (err instanceof R2UploadError) return err;
    throw err;
  }
  throw new Error('Expected promise to reject');
}

describe('validateR2VideoFile / resolveVideoContentType', () => {
  it('accepts every backend allow-listed type', () => {
    for (const type of ['video/mp4', 'video/x-matroska', 'video/webm', 'video/quicktime', 'video/x-msvideo']) {
      expect(validateR2VideoFile({ name: 'a.bin', type, size: 1 })).toEqual({ ok: true, contentType: type });
    }
  });

  it('maps browser alias video/avi to video/x-msvideo', () => {
    expect(resolveVideoContentType({ name: 'a.avi', type: 'video/avi' })).toBe('video/x-msvideo');
  });

  it('falls back to the extension when the browser reports no type (e.g. .mkv)', () => {
    expect(resolveVideoContentType({ name: 'Movie.MKV', type: '' })).toBe('video/x-matroska');
    expect(resolveVideoContentType({ name: 'clip.mov', type: 'application/octet-stream' })).toBe('video/quicktime');
  });

  it('rejects disallowed types even with a video extension', () => {
    expect(validateR2VideoFile({ name: 'poster.mp4', type: 'image/png', size: 5 }))
      .toEqual({ ok: false, reason: 'invalid_type' });
    expect(validateR2VideoFile({ name: 'notes.txt', type: '', size: 5 }))
      .toEqual({ ok: false, reason: 'invalid_type' });
  });

  it('rejects empty and oversize files', () => {
    expect(validateR2VideoFile({ name: 'a.mp4', type: 'video/mp4', size: 0 }))
      .toEqual({ ok: false, reason: 'empty' });
    expect(validateR2VideoFile({ name: 'a.mp4', type: 'video/mp4', size: 101 }, 100))
      .toEqual({ ok: false, reason: 'too_large' });
    expect(validateR2VideoFile({ name: 'a.mp4', type: 'video/mp4', size: 100 }, 100).ok).toBe(true);
  });
});

describe('createR2UploadSession', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('POSTs the exact backend payload with the bearer token', async () => {
    const body = {
      session: makeSession(),
      upload_url: FAKE_PUT_URL,
      upload_method: 'PUT',
      upload_headers: { 'Content-Type': 'video/mp4' },
      expires_in_seconds: 900,
    };
    fetchMock.mockResolvedValue(jsonResponse(201, body));

    const result = await createR2UploadSession(MOVIE_ID, { filename: 'clip.mp4', content_type: 'video/mp4', size: 10 });

    expect(result).toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API}/admin/movies/${MOVIE_ID}/uploads`);
    expect(init.method).toBe('POST');
    expect(init.headers.Authorization).toBe('Bearer test-token');
    expect(JSON.parse(init.body)).toEqual({ filename: 'clip.mp4', content_type: 'video/mp4', size: 10 });
  });

  it.each([
    [401, { detail: 'Not authenticated' }, 'unauthorized', false],
    [403, { detail: 'Admin only' }, 'forbidden', false],
    [404, { detail: 'Movie not found' }, 'not_found', false],
    [400, { detail: 'Video file too large. Maximum size is 100 bytes.' }, 'too_large', false],
    [502, { detail: 'Could not create upload URL.' }, 'storage_error', true],
    [503, { detail: 'R2 storage is not configured.' }, 'unavailable', true],
  ])('maps HTTP %i to kind', async (status, body, kind, retryable) => {
    fetchMock.mockResolvedValue(jsonResponse(status, body));
    const err = await captureError(createR2UploadSession(MOVIE_ID, { filename: 'a.mp4', content_type: 'video/mp4', size: 1 }));
    expect(err.stage).toBe('presign');
    expect(err.kind).toBe(kind);
    expect(err.status).toBe(status);
    expect(err.retryable).toBe(retryable);
    expect(err.message).toBe(body.detail);
  });

  it('reads the first message from a FastAPI 422 validation array', async () => {
    fetchMock.mockResolvedValue(jsonResponse(422, { detail: [{ msg: 'content_type must be one of: ...' }] }));
    const err = await captureError(createR2UploadSession(MOVIE_ID, { filename: 'a', content_type: 'x', size: 1 }));
    expect(err.kind).toBe('validation');
    expect(err.message).toBe('content_type must be one of: ...');
  });

  it('reports network failures', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const err = await captureError(createR2UploadSession(MOVIE_ID, { filename: 'a.mp4', content_type: 'video/mp4', size: 1 }));
    expect(err).toMatchObject({ stage: 'presign', kind: 'network' });
  });
});

describe('putFileToR2', () => {
  beforeEach(() => {
    FakeXHR.reset();
    vi.stubGlobal('XMLHttpRequest', FakeXHR);
  });
  afterEach(() => vi.unstubAllGlobals());

  const file = new File([new Uint8Array(10)], 'clip.mp4', { type: 'video/mp4' });

  it('PUTs the file with exactly the signed headers and no Authorization', async () => {
    const handle = putFileToR2(FAKE_PUT_URL, file, { 'Content-Type': 'video/mp4' });
    const xhr = FakeXHR.last();
    expect(xhr.method).toBe('PUT');
    expect(xhr.url).toBe(FAKE_PUT_URL);
    expect(xhr.requestHeaders).toEqual({ 'Content-Type': 'video/mp4' });
    expect(xhr.body).toBe(file);
    xhr.respond(200);
    await expect(handle.promise).resolves.toBeUndefined();
  });

  it('reports real transferred bytes', async () => {
    const onProgress = vi.fn();
    const handle = putFileToR2(FAKE_PUT_URL, file, {}, onProgress);
    const xhr = FakeXHR.last();
    xhr.progress(3, 10);
    xhr.progress(10, 10);
    xhr.respond(200);
    await handle.promise;
    expect(onProgress.mock.calls.map((c) => c[0])).toEqual([
      { loaded: 3, total: 10 },
      { loaded: 10, total: 10 },
    ]);
  });

  it('classifies an expired presigned URL', async () => {
    const handle = putFileToR2(FAKE_PUT_URL, file, {});
    FakeXHR.last().respond(403, '<Error><Code>AccessDenied</Code><Message>Request has expired</Message></Error>');
    const err = await captureError(handle.promise);
    expect(err).toMatchObject({ stage: 'put', kind: 'expired', status: 403 });
    expect(err.message).not.toContain('AccessDenied'); // raw S3 XML is not surfaced
  });

  it('classifies other R2 rejections as put_failed', async () => {
    const handle = putFileToR2(FAKE_PUT_URL, file, {});
    FakeXHR.last().respond(500, '<Error/>');
    expect(await captureError(handle.promise)).toMatchObject({ stage: 'put', kind: 'put_failed', status: 500 });
  });

  it('classifies network interruption', async () => {
    const handle = putFileToR2(FAKE_PUT_URL, file, {});
    FakeXHR.last().failNetwork();
    expect(await captureError(handle.promise)).toMatchObject({ stage: 'put', kind: 'network' });
  });

  it('aborts via the returned handle', async () => {
    const handle = putFileToR2(FAKE_PUT_URL, file, {});
    handle.abort();
    expect(FakeXHR.last().aborted).toBe(true);
    expect(await captureError(handle.promise)).toMatchObject({ stage: 'put', kind: 'aborted' });
  });

  it('never logs the presigned URL', async () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((m) => vi.spyOn(console, m));
    const handle = putFileToR2(FAKE_PUT_URL, file, {});
    FakeXHR.last().failNetwork();
    await captureError(handle.promise);
    for (const spy of spies) {
      for (const call of spy.mock.calls) expect(JSON.stringify(call)).not.toContain('presigned-put');
      spy.mockRestore();
    }
  });
});

describe('completeR2UploadSession', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('POSTs to the completion endpoint and returns the session', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, makeSession({ status: 'completed', actual_size: 10 })));
    const session = await completeR2UploadSession(MOVIE_ID, SESSION_ID);
    expect(session.status).toBe('completed');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API}/admin/movies/${MOVIE_ID}/uploads/${SESSION_ID}/complete`);
    expect(init.method).toBe('POST');
    expect(init.headers.Authorization).toBe('Bearer test-token');
  });

  it.each([
    [409, 'Uploaded object not found. Finish the upload, then retry completion.', 'object_missing', true],
    [409, 'Upload session expired', 'expired', false],
    [409, 'Upload session is failed', 'conflict', false],
    [422, 'Uploaded size 9 bytes does not match declared size 10 bytes.', 'mismatch', false],
    [502, 'Could not verify upload with storage.', 'storage_error', true],
    [503, 'R2 storage is not configured.', 'unavailable', true],
    [401, 'Not authenticated', 'unauthorized', false],
    [403, 'Upload session belongs to another user', 'forbidden', false],
    [404, 'Upload session not found', 'not_found', false],
  ])('maps HTTP %i "%s"', async (status, detail, kind, retryable) => {
    fetchMock.mockResolvedValue(jsonResponse(status, { detail }));
    const err = await captureError(completeR2UploadSession(MOVIE_ID, SESSION_ID));
    expect(err).toMatchObject({ stage: 'complete', kind, status, retryable });
  });

  it('treats a dropped completion request as retryable (endpoint is idempotent)', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    expect(await captureError(completeR2UploadSession(MOVIE_ID, SESSION_ID)))
      .toMatchObject({ stage: 'complete', kind: 'network', retryable: true });
  });
});

describe('machine-readable error codes', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  // The detail text is deliberately unrelated so only the code can drive the result.
  it.each([
    [409, 'upload_object_missing', 'object_missing', true],
    [409, 'upload_session_expired', 'expired', false],
    [409, 'upload_session_not_pending', 'conflict', false],
    [422, 'upload_verification_failed', 'mismatch', false],
    [502, 'storage_unavailable', 'storage_error', true],
    [503, 'storage_not_configured', 'unavailable', true],
    [403, 'upload_session_forbidden', 'forbidden', false],
    [404, 'upload_session_not_found', 'not_found', false],
  ])('completion HTTP %i code=%s → %s (retryable=%s)', async (status, code, kind, retryable) => {
    fetchMock.mockResolvedValue(jsonResponse(status, { detail: 'Localised or reworded text', code }));
    const err = await captureError(completeR2UploadSession(MOVIE_ID, SESSION_ID));
    expect(err).toMatchObject({ stage: 'complete', kind, status, retryable, code });
  });

  it('reworded detail no longer breaks the retry decision', async () => {
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: 'Object pas encore trouvé', code: 'upload_object_missing' }));
    const err = await captureError(completeR2UploadSession(MOVIE_ID, SESSION_ID));
    expect(err.retryable).toBe(true);
  });

  it('falls back to status/text classification for unknown codes', async () => {
    fetchMock.mockResolvedValue(jsonResponse(502, { detail: 'x', code: 'some_future_code' }));
    const err = await captureError(completeR2UploadSession(MOVIE_ID, SESSION_ID));
    expect(err).toMatchObject({ kind: 'storage_error', retryable: true, code: 'some_future_code' });
  });

  it.each([
    [400, 'upload_too_large', 'too_large', false],
    [404, 'movie_not_found', 'not_found', false],
    [502, 'presign_failed', 'storage_error', true],
    [503, 'storage_not_configured', 'unavailable', true],
  ])('initiation HTTP %i code=%s → %s', async (status, code, kind, retryable) => {
    fetchMock.mockResolvedValue(jsonResponse(status, { detail: 'text', code }));
    const err = await captureError(createR2UploadSession(MOVIE_ID, { filename: 'a.mp4', content_type: 'video/mp4', size: 1 }));
    expect(err).toMatchObject({ stage: 'presign', kind, status, retryable, code });
  });
});
