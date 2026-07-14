import { describe, it, expect } from 'vitest';
import { resolveMediaUrl } from '../config';

describe('resolveMediaUrl', () => {
  // ── Null / undefined / empty ──────────────────────────────────────

  it('returns null for null', () => {
    expect(resolveMediaUrl(null)).toBeNull();
  });

  it('returns null for undefined', () => {
    expect(resolveMediaUrl(undefined)).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(resolveMediaUrl('')).toBeNull();
  });

  // ── Relative paths ────────────────────────────────────────────────

  it('adds leading slash to relative media path', () => {
    expect(resolveMediaUrl('media/videos/hls/abc/master.m3u8'))
      .toBe('/media/videos/hls/abc/master.m3u8');
  });

  it('adds leading slash to relative poster path', () => {
    expect(resolveMediaUrl('media/images/posters/abc.jpg'))
      .toBe('/media/images/posters/abc.jpg');
  });

  // ── Already root-relative ─────────────────────────────────────────

  it('preserves root-relative path unchanged', () => {
    expect(resolveMediaUrl('/media/videos/hls/abc/master.m3u8'))
      .toBe('/media/videos/hls/abc/master.m3u8');
  });

  it('preserves root-relative poster path', () => {
    expect(resolveMediaUrl('/media/images/posters/abc.jpg'))
      .toBe('/media/images/posters/abc.jpg');
  });

  // ── Stale HTTP URLs ───────────────────────────────────────────────

  it('strips stale HTTP IP URL to /media/ path', () => {
    expect(resolveMediaUrl('http://172.35.53.158/media/videos/hls/abc/master.m3u8'))
      .toBe('/media/videos/hls/abc/master.m3u8');
  });

  it('strips stale localhost URL to /media/ path', () => {
    expect(resolveMediaUrl('http://localhost:8000/media/images/posters/test.jpg'))
      .toBe('/media/images/posters/test.jpg');
  });

  it('rejects HTTP URL without /media/ segment', () => {
    expect(resolveMediaUrl('http://172.35.53.158/some/other/path.jpg'))
      .toBeNull();
  });

  // ── Valid HTTPS URLs ──────────────────────────────────────────────

  it('preserves external HTTPS URL', () => {
    const url = 'https://cdn.example.com/posters/movie123.jpg';
    expect(resolveMediaUrl(url)).toBe(url);
  });

  it('preserves same-origin HTTPS URL', () => {
    const url = 'https://laetus.io.vn/media/images/posters/abc.jpg';
    expect(resolveMediaUrl(url)).toBe(url);
  });

  // ── No Mixed Content ──────────────────────────────────────────────

  it('never returns an http:// URL', () => {
    const inputs = [
      'http://172.35.53.158/media/videos/hls/abc/master.m3u8',
      'http://localhost:8000/media/images/posters/test.jpg',
      '/media/images/posters/test.jpg',
      'media/images/posters/test.jpg',
      'https://cdn.example.com/poster.jpg',
      null,
      undefined,
      '',
    ];

    for (const input of inputs) {
      const result = resolveMediaUrl(input);
      if (result !== null) {
        expect(result).not.toMatch(/^http:\/\//);
      }
    }
  });

  // ── No /media/media/ duplication ──────────────────────────────────

  it('does not duplicate /media/ prefix', () => {
    const result = resolveMediaUrl('media/videos/example.m3u8');
    expect(result).toBe('/media/videos/example.m3u8');
    expect(result).not.toContain('/media/media/');
  });
});
