import { describe, it, expect, beforeEach } from 'vitest';
import {
  getGuestFavoriteIds,
  addGuestFavorite,
  removeGuestFavorite,
  clearGuestFavorites,
} from '../services/favoriteService';

const GUEST_FAVORITES_KEY = 'guest_favorite_ids';

describe('Guest Favorites — localStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // ── getGuestFavoriteIds ─────────────────────────────────────────

  it('returns empty array when no data exists', () => {
    expect(getGuestFavoriteIds()).toEqual([]);
  });

  it('returns empty array for invalid JSON', () => {
    localStorage.setItem(GUEST_FAVORITES_KEY, 'not-json');
    expect(getGuestFavoriteIds()).toEqual([]);
  });

  it('returns empty array for non-array JSON', () => {
    localStorage.setItem(GUEST_FAVORITES_KEY, '{"id":"1"}');
    expect(getGuestFavoriteIds()).toEqual([]);
  });

  it('filters out non-string values', () => {
    localStorage.setItem(GUEST_FAVORITES_KEY, '["a", 123, null, "b"]');
    expect(getGuestFavoriteIds()).toEqual(['a', 'b']);
  });

  it('returns valid string array', () => {
    localStorage.setItem(GUEST_FAVORITES_KEY, '["movie-1","movie-2"]');
    expect(getGuestFavoriteIds()).toEqual(['movie-1', 'movie-2']);
  });

  // ── addGuestFavorite ────────────────────────────────────────────

  it('adds a movie ID to empty favorites', () => {
    addGuestFavorite('movie-1');
    expect(getGuestFavoriteIds()).toEqual(['movie-1']);
  });

  it('appends a movie ID to existing favorites', () => {
    addGuestFavorite('movie-1');
    addGuestFavorite('movie-2');
    expect(getGuestFavoriteIds()).toEqual(['movie-1', 'movie-2']);
  });

  it('deduplicates — does not add same ID twice', () => {
    addGuestFavorite('movie-1');
    addGuestFavorite('movie-1');
    expect(getGuestFavoriteIds()).toEqual(['movie-1']);
  });

  // ── removeGuestFavorite ─────────────────────────────────────────

  it('removes a movie ID from favorites', () => {
    addGuestFavorite('movie-1');
    addGuestFavorite('movie-2');
    removeGuestFavorite('movie-1');
    expect(getGuestFavoriteIds()).toEqual(['movie-2']);
  });

  it('does nothing when removing a non-existent ID', () => {
    addGuestFavorite('movie-1');
    removeGuestFavorite('movie-999');
    expect(getGuestFavoriteIds()).toEqual(['movie-1']);
  });

  // ── clearGuestFavorites ─────────────────────────────────────────

  it('clears all guest favorites from localStorage', () => {
    addGuestFavorite('movie-1');
    addGuestFavorite('movie-2');
    clearGuestFavorites();
    expect(getGuestFavoriteIds()).toEqual([]);
    expect(localStorage.getItem(GUEST_FAVORITES_KEY)).toBeNull();
  });

  it('clearing empty favorites is a no-op', () => {
    clearGuestFavorites();
    expect(getGuestFavoriteIds()).toEqual([]);
  });
});
