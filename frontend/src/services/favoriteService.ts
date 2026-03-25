const STORAGE_KEY = 'favoriteMovieIds';

/**
 * Reads the list of favorite movie IDs from localStorage.
 * Returns an empty array if the key doesn't exist or the data is corrupted.
 */
export const getFavoriteMovieIds = (): string[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === 'string');
  } catch {
    return [];
  }
};

/**
 * Checks whether a movie ID is in the favorites list.
 * Returns false for falsy IDs.
 */
export const isFavoriteMovie = (id: string): boolean => {
  if (!id) return false;
  return getFavoriteMovieIds().includes(id);
};

/**
 * Toggles a movie ID in the favorites list (add if absent, remove if present).
 * Returns the updated list. Does nothing for falsy IDs.
 */
export const toggleFavoriteMovie = (id: string): string[] => {
  if (!id) return getFavoriteMovieIds();

  const current = getFavoriteMovieIds();
  const index = current.indexOf(id);

  const updated = index === -1
    ? [...current, id]
    : current.filter((fid) => fid !== id);

  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return updated;
};
