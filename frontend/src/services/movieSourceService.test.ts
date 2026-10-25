import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MovieSourceStatusError, getMovieSourceStatus } from './movieSourceService';

vi.mock('./authService', () => ({ getToken: () => 'admin-token' }));

const API = 'http://localhost:8000/api/v1';

describe('getMovieSourceStatus', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('GETs the admin source endpoint with the bearer token', async () => {
    const body = {
      movie_id: 'm1', source_storage: 'r2', source_available: true,
      processing_status: 'no_video', hls_ready: false, hls_processing_supported: false,
    };
    fetchMock.mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    await expect(getMovieSourceStatus('m1')).resolves.toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API}/admin/movies/m1/source`);
    expect(init.headers.Authorization).toBe('Bearer admin-token');
  });

  it.each([
    [401, { detail: 'Not authenticated' }, null],
    [403, { detail: "The user doesn't have enough privileges" }, null],
    [404, { detail: 'Movie not found', code: 'movie_not_found' }, 'movie_not_found'],
  ])('throws MovieSourceStatusError for HTTP %i', async (status, body, code) => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(body), { status }));
    const err = await getMovieSourceStatus('m1').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(MovieSourceStatusError);
    expect(err).toMatchObject({ status, code, message: body.detail });
  });

  it('reports network failures with a null status', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const err = await getMovieSourceStatus('m1').catch((e: unknown) => e);
    expect(err).toMatchObject({ name: 'MovieSourceStatusError', status: null });
  });
});
