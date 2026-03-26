"""
Explanation Layer for Recommendations

Generates human-readable reasons for why a movie was recommended,
based on the user's interaction profile.
"""


def generate_reason(interaction_summary: dict, score: float) -> str:
    """
    Generate a concise explanation for a recommendation.

    Uses the user's interaction summary to determine the dominant signal,
    then combines it with the similarity score.

    Args:
        interaction_summary: { ratings_count, favorites_count, watched_count }
        score: cosine similarity score (0-1)

    Returns:
        Human-readable reason string.
    """
    ratings_count = interaction_summary.get("ratings_count", 0)
    favorites_count = interaction_summary.get("favorites_count", 0)
    watched_count = interaction_summary.get("watched_count", 0)

    # Determine the dominant signal for the explanation
    # Priority: ratings > favorites > watch history
    if ratings_count > 0 and ratings_count >= favorites_count:
        source = "Based on your ratings"
    elif favorites_count > 0:
        source = "Based on your favorites"
    elif watched_count > 0:
        source = "Similar to movies you watched"
    else:
        return "Recommended for you"

    # Add confidence qualifier based on score
    if score >= 0.5:
        confidence = "Strong match"
    elif score >= 0.2:
        confidence = "Good match"
    else:
        confidence = "You might like this"

    return f"{source} · {confidence}"
