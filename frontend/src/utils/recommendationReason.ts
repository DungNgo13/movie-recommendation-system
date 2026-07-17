import { TFunction } from "i18next";

const knownReasons: Record<string, string> = {
  // Combinations for "Based on your ratings"
  "Based on your ratings · Strong match": "recommendation:reasons.ratings_strong",
  "Based on your ratings · Good match": "recommendation:reasons.ratings_good",
  "Based on your ratings · You might like this": "recommendation:reasons.ratings_might_like",

  // Combinations for "Based on your favorites"
  "Based on your favorites · Strong match": "recommendation:reasons.favorites_strong",
  "Based on your favorites · Good match": "recommendation:reasons.favorites_good",
  "Based on your favorites · You might like this": "recommendation:reasons.favorites_might_like",

  // Combinations for "Similar to movies you watched"
  "Similar to movies you watched · Strong match": "recommendation:reasons.history_strong",
  "Similar to movies you watched · Good match": "recommendation:reasons.history_good",
  "Similar to movies you watched · You might like this": "recommendation:reasons.history_might_like",

  // Defaults and fallbacks
  "Recommended for you": "recommendation:reasons.default",
  "Popular movie — rate or favorite some movies for personalized picks!": "recommendation:reasons.fallback"
};

export function getLocalizedRecommendationReason(reason: string, t: TFunction): string {
  const key = knownReasons[reason];
  if (!key) {
    return reason; // Fallback to raw backend text if not found
  }
  return t(key);
}
