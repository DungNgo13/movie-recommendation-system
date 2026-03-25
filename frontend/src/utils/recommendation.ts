import type { MovieListItem } from '../models';

/** Words too common/short to be meaningful for title matching */
const STOP_WORDS = new Set([
  'the', 'a', 'an', 'of', 'and', 'in', 'to', 'for', 'is', 'on', 'at', 'by',
  'or', 'it', 'as', 'be', 'no', 'do', 'so', 'if', 'up', 'my', 'we', 'he',
  'me', 'us', 'am', 'vs', 'ii', 'la', 'le', 'el', 'de', 'du', 'un', 'en',
]);

/**
 * Extracts meaningful keywords from a movie title.
 * Lowercases, removes non-alphanumeric chars, filters stop words and short tokens.
 */
export const extractKeywords = (title: string): string[] => {
  if (!title) return [];
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter((word) => word.length > 1 && !STOP_WORDS.has(word));
};

interface ScoringContext {
  titleKeywords: string[];
  releaseYear: number | null;
}

/**
 * Calculates a recommendation score for a candidate movie against the current movie.
 *
 * Scoring:
 * - +3 per matching title keyword
 * - +2 if same release year
 * - +1 if release year within 1–2 years
 */
export const calculateScore = (
  candidate: MovieListItem,
  context: ScoringContext,
): number => {
  let score = 0;

  // Title keyword matching
  const candidateKeywords = extractKeywords(candidate.title);
  for (const keyword of context.titleKeywords) {
    if (candidateKeywords.includes(keyword)) {
      score += 3;
    }
  }

  // Release year proximity
  if (context.releaseYear !== null && candidate.release_year !== null) {
    const diff = Math.abs(context.releaseYear - candidate.release_year);
    if (diff === 0) {
      score += 2;
    } else if (diff <= 2) {
      score += 1;
    }
  }

  return score;
};

/**
 * Returns a list of recommended movies for a given movie, sorted by score descending.
 * Excludes the current movie. Returns at most `limit` results.
 * Falls back to other movies if no good matches are found.
 */
export const getRecommendations = (
  currentMovieId: string,
  currentTitle: string,
  currentReleaseYear: number | null,
  allMovies: MovieListItem[],
  limit = 4,
): MovieListItem[] => {
  if (!currentMovieId || !allMovies.length) return [];

  const context: ScoringContext = {
    titleKeywords: extractKeywords(currentTitle),
    releaseYear: currentReleaseYear,
  };

  const candidates = allMovies.filter((m) => m.id !== currentMovieId);

  const scored = candidates.map((movie) => ({
    movie,
    score: calculateScore(movie, context),
  }));

  scored.sort((a, b) => b.score - a.score);

  return scored.slice(0, limit).map((s) => s.movie);
};
