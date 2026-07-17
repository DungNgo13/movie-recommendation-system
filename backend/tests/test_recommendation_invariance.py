import pytest
from app.models.movie import Movie
from app.services.recommendation.movie_profile import build_movie_text

def test_vietnamese_metadata_does_not_affect_recommendation_profile():
    """
    Ensure that adding or modifying Vietnamese display metadata
    (title_vi, overview_vi, keyword_labels_vi) does NOT alter the
    text corpus generated for TF-IDF vectorization.
    """
    # 1. Base movie with only English/canonical metadata
    movie = Movie(
        title="FPV Forest Flight",
        overview="A cinematic FPV flight through a green forest.",
        genres=["Documentary", "Adventure"],
        keywords=["forest", "fpv", "nature"],
        cast=["Drone Camera"],
        director="Pexels Creator"
    )

    # Generate the baseline profile
    english_profile_before = build_movie_text(movie)

    # 2. Add Vietnamese display metadata
    movie.title_vi = "Chuyến bay FPV xuyên rừng"
    movie.overview_vi = "Chuyến bay FPV điện ảnh xuyên qua khu rừng xanh."
    movie.keyword_labels_vi = {
        "forest": "rừng",
        "fpv": "FPV",
        "nature": "thiên nhiên"
    }

    # Generate the profile again
    english_profile_after = build_movie_text(movie)

    # 3. Assert exact invariance
    assert english_profile_before == english_profile_after

    # 4. Assert absence of translated text in the profile
    assert "Chuyến bay FPV xuyên rừng" not in english_profile_after
    assert "Chuyến bay FPV điện ảnh" not in english_profile_after
    assert "rừng" not in english_profile_after
    assert "thiên nhiên" not in english_profile_after

    # Verify the English content is actually what we expect
    assert "FPV Forest Flight" in english_profile_after
    assert "A cinematic FPV flight" in english_profile_after
    assert "forest" in english_profile_after
