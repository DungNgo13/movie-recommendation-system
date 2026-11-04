"""
Comprehensive offline unit and integration tests for Phase 8B Semantic Embeddings,
Deterministic Text Builder, Versioned Vector Cache, Semantic User-Profile & Ranking
Engine, Production Feature Flag Fallback, and Offline Evaluation Adapter.

All tests run 100% offline without network calls or large neural model weight downloads.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models.movie import Movie
from app.models.rating import Rating
from app.models.user import User
from app.models.user_favorite import UserFavorite as Favorite
from app.models.watch_history import WatchHistory
from app.recommendation_evaluation.dataset import (
    EvaluationDataset,
    MovieMetadata,
    RatingEvent,
)
from app.recommendation_evaluation.semantic_eval import (
    OfflineSemanticRecommender,
    SemanticModelConfig,
    compute_extended_paired_comparison,
    evaluate_recommender,
)
from app.services.recommendation.embedding_cache import (
    check_cache_staleness,
    get_embedding_cache_stats,
    invalidate_embedding_cache,
    load_embedding_artifact,
    register_in_process_artifact,
    save_embedding_artifact,
)
from app.services.recommendation.embeddings import (
    DETERMINISTIC_TEST_SPEC,
    DeterministicHashEncoder,
    generate_catalog_embeddings,
    l2_normalize_rows,
    mean_pool_and_normalize,
    validate_embedding_matrix,
)
from app.services.recommendation.engine import get_recommendations
from app.services.recommendation.semantic_engine import (
    build_semantic_user_profile,
    compute_user_interaction_weights,
    get_recommendation_strategy,
    rank_semantic_candidates,
)
from app.services.recommendation.text_builder import (
    deduplicate_phrases,
    normalize_text_value,
    prepare_catalog_documents,
    prepare_movie_document,
)
from app.services.recommendation.vectorizer import invalidate_cache


@pytest.fixture()
def db_session():
    """Isolated in-memory SQLite database session for recommendation tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionTesting()
    invalidate_cache()
    invalidate_embedding_cache()
    try:
        yield session
    finally:
        invalidate_cache()
        invalidate_embedding_cache()
        session.close()
        Base.metadata.drop_all(bind=engine)


# ── 1–4 & 20: Deterministic Movie Text Builder Tests ──────────────────────────

def test_text_builder_deterministic_output():
    """1. Movie text builder produces identical deterministic text and SHA-256 across calls."""
    movie_data = {
        "id": "101",
        "title": "Inception",
        "original_title": "Inception",
        "title_vi": "Kẻ Đánh Cắp Giấc Mơ",
        "genres": ["Action", "Sci-Fi", "action"],
        "keywords": ["dream", "heist", "subconscious", "DREAM"],
        "overview": "A thief who steals corporate secrets through dream-sharing technology.",
        "overview_vi": "Một tên trộm đánh cắp bí mật công ty thông qua công nghệ chia sẻ giấc mơ.",
        "cast": ["Leonardo DiCaprio", "Joseph Gordon-Levitt", "Ellen Page"],
        "director": "Christopher Nolan",
        "metadata_source": "tmdb",
        "metadata_version": 3,
        "metadata_enrichment_status": "applied",
    }
    doc1 = prepare_movie_document(movie_data, language_policy="en_only")
    doc2 = prepare_movie_document(movie_data, language_policy="en_only")

    assert doc1.text == doc2.text
    assert doc1.text_sha256 == doc2.text_sha256
    assert doc1.metadata_source == "tmdb"
    assert doc1.metadata_version == 3
    assert doc1.enrichment_status == "applied"
    # Deduplicated genres and keywords
    assert "Genres: Action, Sci-Fi." in doc1.text
    assert "Keywords: dream, heist, subconscious." in doc1.text
    # Identical original_title is not repeated
    assert "Original title:" not in doc1.text


def test_text_builder_missing_field_handling():
    """2. Missing and empty fields are handled safely without fabricated placeholders."""
    sparse_movie = {
        "id": "202",
        "title": "Mystery Reel (1928)",
        "genres": ["(no genres listed)", ""],
        "keywords": None,
        "overview": None,
        "cast": [],
        "director": "   ",
    }
    doc = prepare_movie_document(sparse_movie, language_policy="en_only")
    assert doc.text == "Title: Mystery Reel (1928)."
    assert "title" in doc.fields_present
    assert "overview" in doc.fields_missing
    assert "director" in doc.fields_missing
    assert "genres" in doc.fields_missing
    assert doc.completeness_ratio == pytest.approx(1.0 / 9.0)
    assert not doc.is_empty

    # Completely empty movie record
    empty_movie = {"id": "203", "title": "   "}
    empty_doc = prepare_movie_document(empty_movie, language_policy="en_only")
    assert empty_doc.text == ""
    assert empty_doc.is_empty is True
    assert empty_doc.is_minimal is True
    assert empty_doc.token_count == 0


def test_text_builder_unicode_and_vietnamese_normalization():
    """3. Unicode NFD decomposed Vietnamese diacritics are normalized to NFC and collapsed."""
    # Decomposed 'Hố' ('o' + combining circumflex + combining acute)
    decomposed_vi = "Ho\u0302\u0301   \u0110en   Tu\u031b\u0309   Tha\u0302\u0300n"
    normalized = normalize_text_value(decomposed_vi)
    assert normalized == "Hố Đen Tử Thần"

    phrases = deduplicate_phrases(["  Khoa học viễn tưởng ", "khoa học viễn tưởng", "Hành động"])
    assert phrases == ["Khoa học viễn tưởng", "Hành động"]


def test_text_builder_language_policy_and_config_separation():
    """4 & 20. Language policy separates en_only, multilingual, tfidf_original, and tfidf_enriched."""
    movie = {
        "id": "303",
        "title": "Spirited Away",
        "original_title": "千と千尋の神隠し",
        "title_vi": "Vùng Đất Linh Hồn",
        "genres": ["Animation", "Fantasy"],
        "keywords": ["spirit world", "bathhouse"],
        "overview": "Chihiro enters a world ruled by gods and witches.",
        "overview_vi": "Chihiro lạc vào thế giới linh hồn bí ẩn.",
        "cast": ["Rumi Hiiragi"],
        "director": "Hayao Miyazaki",
    }

    doc_en = prepare_movie_document(movie, language_policy="en_only")
    doc_multi = prepare_movie_document(movie, language_policy="multilingual")
    doc_tfidf_orig = prepare_movie_document(movie, language_policy="tfidf_original")
    doc_tfidf_enr = prepare_movie_document(movie, language_policy="tfidf_enriched")

    # en_only must exclude Vietnamese title_vi and overview_vi
    assert "Vùng Đất Linh Hồn" not in doc_en.text
    assert "Chihiro lạc vào" not in doc_en.text
    assert "Original title: 千と千尋の神隠し." in doc_en.text

    # multilingual must include Vietnamese title_vi and overview_vi
    assert "Vietnamese title: Vùng Đất Linh Hồn." in doc_multi.text
    assert "Vietnamese overview: Chihiro lạc vào thế giới linh hồn bí ẩn." in doc_multi.text

    # tfidf_original excludes overview, cast, director; tfidf_enriched includes them
    assert "Hayao Miyazaki" not in doc_tfidf_orig.text
    assert "Chihiro enters" not in doc_tfidf_orig.text
    assert "director Hayao Miyazaki" in doc_tfidf_enr.text
    assert "actor Rumi Hiiragi" in doc_tfidf_enr.text
    assert "Chihiro enters" in doc_tfidf_enr.text


# ── 5–8: Embedding Shape, L2 Norm, NaN/Inf, and Zero-Vector Tests ─────────────

def test_embedding_shape_and_l2_normalization():
    """5 & 6. Batch encoder outputs (N, D) float32 matrix with unit L2 norms."""
    encoder = DeterministicHashEncoder(spec=DETERMINISTIC_TEST_SPEC)
    texts = [
        "Title: The Matrix. Genres: Action, Sci-Fi. Keywords: virtual reality, cyberpunk.",
        "Title: Toy Story. Genres: Animation, Comedy, Family. Keywords: toys, friendship.",
    ]
    matrix = encoder.encode(texts, normalize=True)
    assert matrix.shape == (2, 384)
    assert matrix.dtype == np.float32

    norms = np.linalg.norm(matrix, axis=1)
    np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-6)

    validation = validate_embedding_matrix(matrix, expected_rows=2, expected_dim=384)
    assert validation["all_finite"] is True
    assert validation["zero_vector_count"] == 0
    assert validation["max_unit_norm_deviation"] < 1e-6


def test_embedding_nan_inf_and_shape_rejection():
    """7. validate_embedding_matrix rejects NaN, Inf, and wrong dimensions."""
    good = np.ones((3, 384), dtype=np.float32)
    good = l2_normalize_rows(good)

    with pytest.raises(ValueError, match="shape mismatch"):
        validate_embedding_matrix(good, expected_rows=4, expected_dim=384)

    bad_nan = good.copy()
    bad_nan[1, 10] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_embedding_matrix(bad_nan, expected_rows=3, expected_dim=384)

    bad_inf = good.copy()
    bad_inf[2, 0] = np.inf
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_embedding_matrix(bad_inf, expected_rows=3, expected_dim=384)


def test_zero_vector_detection_and_mean_pooling():
    """8. Empty movie texts produce safe zero vectors and are tracked in zero_vector_movie_ids."""
    encoder = DeterministicHashEncoder(spec=DETERMINISTIC_TEST_SPEC)
    matrix = encoder.encode(["Title: Inception.", "   "], normalize=True)

    assert np.linalg.norm(matrix[0]) == pytest.approx(1.0, abs=1e-6)
    assert np.linalg.norm(matrix[1]) == 0.0

    val = validate_embedding_matrix(
        matrix, expected_rows=2, expected_dim=384, movie_ids=["m1", "m2"]
    )
    assert val["zero_vector_count"] == 1
    assert val["zero_vector_movie_ids"] == ["m2"]

    # Test mean_pool_and_normalize with attention mask
    tok_embs = np.ones((1, 4, 8), dtype=np.float32)
    mask = np.array([[1, 1, 0, 0]], dtype=np.int64)
    pooled = mean_pool_and_normalize(tok_embs, mask, normalize=True)
    assert pooled.shape == (1, 8)
    assert np.linalg.norm(pooled[0]) == pytest.approx(1.0, abs=1e-6)


# ── 9–11: Versioned Cache Save/Load, Checksum Mismatch, and Staleness Tests ───

def test_versioned_cache_save_load_and_checksum_verification(tmp_path: Path):
    """9 & 10. Versioned cache saves/loads artifacts and rejects corrupted checksums."""
    movies = [
        {"id": "1", "title": "The Shawshank Redemption", "genres": ["Drama"], "metadata_version": 1},
        {"id": "2", "title": "Pulp Fiction", "genres": ["Crime"], "metadata_version": 2},
    ]
    gen = generate_catalog_embeddings(movies, model_key="deterministic_test")
    art = save_embedding_artifact(
        cache_dir=tmp_path,
        dataset_id="unit_test_catalog",
        spec=gen["spec"],
        vectors=gen["vectors"],
        documents=gen["documents"],
        metadata_snapshot_checksum=gen["snapshot_summary"]["metadata_snapshot_checksum"],
        generation_duration_seconds=gen["generation_duration_seconds"],
        peak_memory_mb=gen["peak_memory_mb"],
        artifact_id="test_art_v1",
    )

    loaded = load_embedding_artifact(tmp_path, "test_art_v1", verify_checksums=True)
    assert loaded.artifact_id == "test_art_v1"
    assert loaded.movie_ids == ["1", "2"]
    assert loaded.movie_metadata_versions == {"1": 1, "2": 2}
    np.testing.assert_allclose(loaded.vectors, art.vectors, atol=1e-6)

    # Corrupt manifest movie_id_mapping_checksum and verify load raises ValueError
    manifest_path = Path(loaded.manifest_path)
    manifest_text = manifest_path.read_text(encoding="utf-8")
    corrupted = manifest_text.replace(
        loaded.movie_id_mapping_checksum, "0" * 64
    )
    manifest_path.write_text(corrupted, encoding="utf-8")

    with pytest.raises(ValueError, match="mapping checksum mismatch"):
        load_embedding_artifact(tmp_path, "test_art_v1", verify_checksums=True)


def test_stale_metadata_version_detection(tmp_path: Path):
    """11. Incrementing a movie's metadata_version marks the cached artifact stale."""
    movies_v1 = [
        {"id": "10", "title": "Interstellar", "genres": ["Sci-Fi"], "metadata_version": 1},
        {"id": "20", "title": "Arrival", "genres": ["Sci-Fi"], "metadata_version": 1},
    ]
    gen = generate_catalog_embeddings(movies_v1, model_key="deterministic_test")
    art = save_embedding_artifact(
        cache_dir=tmp_path,
        dataset_id="staleness_test",
        spec=gen["spec"],
        vectors=gen["vectors"],
        documents=gen["documents"],
        metadata_snapshot_checksum=gen["snapshot_summary"]["metadata_snapshot_checksum"],
        generation_duration_seconds=gen["generation_duration_seconds"],
        peak_memory_mb=gen["peak_memory_mb"],
    )

    fresh_check = check_cache_staleness(movies_v1, art)
    assert fresh_check["is_stale"] is False
    assert fresh_check["stale_movie_ids"] == []

    # Simulate Phase 8A approved metadata update incrementing metadata_version to 2
    movies_v2 = [
        {"id": "10", "title": "Interstellar", "genres": ["Sci-Fi"], "metadata_version": 2},
        {"id": "20", "title": "Arrival", "genres": ["Sci-Fi"], "metadata_version": 1},
        {"id": "30", "title": "Dune", "genres": ["Sci-Fi"], "metadata_version": 1},
    ]
    stale_check = check_cache_staleness(movies_v2, art)
    assert stale_check["is_stale"] is True
    assert stale_check["has_version_mismatch"] is True
    assert stale_check["stale_movie_ids"] == ["10"]
    assert stale_check["missing_movie_ids"] == ["30"]


# ── 12–18: Semantic User Profile, Ranking, MMR, and Feature Flag Tests ────────

def _seed_movies_and_user(db_session):
    m1 = Movie(
        id=uuid4(),
        title="Blade Runner 2049",
        overview="Young Blade Runner K's discovery of a long-buried secret.",
        genres=["Sci-Fi", "Drama"],
        keywords=["cyberpunk", "android", "dystopia"],
        director="Denis Villeneuve",
        release_date=date(2017, 10, 6),
        processing_status="ready",
        metadata_version=1,
    )
    m2 = Movie(
        id=uuid4(),
        title="The Matrix",
        overview="A computer hacker learns about the true nature of reality.",
        genres=["Sci-Fi", "Action"],
        keywords=["cyberpunk", "virtual reality", "ai"],
        director="Lana Wachowski",
        release_date=date(1999, 3, 31),
        processing_status="ready",
        metadata_version=1,
    )
    m3 = Movie(
        id=uuid4(),
        title="Pride and Prejudice",
        overview="Sparks fly when spirited Elizabeth Bennet meets single, rich Mr. Darcy.",
        genres=["Romance", "Drama"],
        keywords=["period drama", "regency", "marriage"],
        director="Joe Wright",
        release_date=date(2005, 9, 16),
        processing_status="ready",
        metadata_version=1,
    )
    m4 = Movie(
        id=uuid4(),
        title="Ghost in the Shell",
        overview="A cyborg policewoman hunts a mysterious hacker known as the Puppet Master.",
        genres=["Sci-Fi", "Animation"],
        keywords=["cyberpunk", "cyborg", "hacker"],
        director="Mamoru Oshii",
        release_date=date(1995, 11, 18),
        processing_status="ready",
        metadata_version=1,
    )
    user = User(
        id=uuid4(),
        email="phase8b@movsug.test",
        password_hash="hashed_password",
    )
    db_session.add_all([m1, m2, m3, m4, user])
    db_session.commit()
    return user, [m1, m2, m3, m4]


def test_user_profile_weighting_and_negative_rating_suppression(db_session, tmp_path: Path):
    """12 & 13. Semantic user profile matches TF-IDF v1.1 weights and suppresses 1-2 star ratings."""
    user, movies = _seed_movies_and_user(db_session)
    m1, m2, m3, _ = movies

    # User loves m1 (5 stars -> 5.0), dislikes m3 (1 star -> 0.0, even though favorited & watched!)
    db_session.add(Rating(user_id=user.id, movie_id=m1.id, rating=5))
    db_session.add(Rating(user_id=user.id, movie_id=m3.id, rating=1))
    db_session.add(Favorite(user_id=user.id, movie_id=m3.id))
    db_session.add(
        WatchHistory(
            user_id=user.id,
            movie_id=m3.id,
            progress_percent=95,
            watched_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(Favorite(user_id=user.id, movie_id=m2.id))
    db_session.commit()

    weights = compute_user_interaction_weights(db_session, user.id, suppress_negative=True)
    assert weights[str(m1.id)] == 5.0
    assert weights[str(m2.id)] == 3.0
    assert str(m3.id) not in weights  # R2 negative feedback suppression

    gen = generate_catalog_embeddings(movies, model_key="deterministic_test")
    art = save_embedding_artifact(
        cache_dir=tmp_path,
        dataset_id="profile_test",
        spec=gen["spec"],
        vectors=gen["vectors"],
        documents=gen["documents"],
        metadata_snapshot_checksum=gen["snapshot_summary"]["metadata_snapshot_checksum"],
        generation_duration_seconds=gen["generation_duration_seconds"],
        peak_memory_mb=gen["peak_memory_mb"],
    )

    u_vec, diag = build_semantic_user_profile(weights, art)
    assert u_vec is not None
    assert np.linalg.norm(u_vec) == pytest.approx(1.0, abs=1e-6)
    assert diag["used_movies_count"] == 2


def test_semantic_ranking_seen_exclusion_tie_breaking_and_mmr(tmp_path: Path):
    """14, 16, & 17. Seen-item exclusion, deterministic tie-breaking, and MMR re-ranking."""
    # Create 4 synthetic movie vectors where movies "10" and "2" have identical similarity
    v_user = np.zeros(384, dtype=np.float32)
    v_user[0] = 1.0

    vectors = np.zeros((4, 384), dtype=np.float32)
    vectors[0, 0] = 0.9   # movie "10" (seen -> excluded)
    vectors[1, 0] = 0.8   # movie "20" (tied at 0.8)
    vectors[1, 1] = 0.6
    vectors[2, 0] = 0.8   # movie "5"  (tied at 0.8 -> should rank before "20" by numeric ID!)
    vectors[2, 1] = 0.6
    vectors[3, 0] = 0.5   # movie "30" (diverse orthogonal direction)
    vectors[3, 2] = 0.8660254

    docs, snap = prepare_catalog_documents(
        [
            {"id": "10", "title": "M10"},
            {"id": "20", "title": "M20"},
            {"id": "5", "title": "M5"},
            {"id": "30", "title": "M30"},
        ],
        language_policy="en_only",
    )
    # Reorder vectors to match sorted docs order: ["5", "10", "20", "30"]
    ordered_vectors = np.vstack([vectors[2], vectors[0], vectors[1], vectors[3]])
    art = save_embedding_artifact(
        cache_dir=tmp_path,
        dataset_id="tie_mmr_test",
        spec=DETERMINISTIC_TEST_SPEC,
        vectors=ordered_vectors,
        documents=docs,
        metadata_snapshot_checksum=snap["metadata_snapshot_checksum"],
        generation_duration_seconds=0.01,
        peak_memory_mb=1.0,
    )

    ranked, stats = rank_semantic_candidates(
        user_vector=v_user,
        artifact=art,
        candidate_movie_ids=["5", "10", "20", "30"],
        exclude_ids={"10"},
        top_n=3,
        mmr_enabled=False,
    )
    # "10" is excluded; "5" and "20" tie at 0.8 so numeric ID "5" comes first
    assert [mid for mid, _ in ranked] == ["5", "20", "30"]
    assert stats["missing_vector_rate"] == 0.0

    # With MMR enabled and low lambda (0.3), after selecting "5", "20" is identical to "5"
    # so MMR promotes diverse item "30" to rank 2!
    ranked_mmr, _ = rank_semantic_candidates(
        user_vector=v_user,
        artifact=art,
        candidate_movie_ids=["5", "10", "20", "30"],
        exclude_ids={"10"},
        top_n=3,
        mmr_enabled=True,
        mmr_lambda=0.3,
        mmr_pool_size=10,
    )
    assert [mid for mid, _ in ranked_mmr] == ["5", "30", "20"]


def test_production_feature_flag_cold_start_and_safe_fallback(
    db_session, tmp_path: Path, monkeypatch
):
    """15 & 18. Feature flag defaults to tfidf_v1_1, serves semantic when cached, and falls back when missing/stale."""
    user, movies = _seed_movies_and_user(db_session)
    m1, m2, m3, m4 = movies

    # Default strategy is tfidf_v1_1
    monkeypatch.delenv("RECOMMENDATION_STRATEGY", raising=False)
    assert get_recommendation_strategy() == "tfidf_v1_1"

    # Cold-start user under semantic strategy -> deterministic cold-start fallback
    gen = generate_catalog_embeddings(movies, model_key="deterministic_test")
    art = save_embedding_artifact(
        cache_dir=tmp_path,
        dataset_id="prod_flag_test",
        spec=gen["spec"],
        vectors=gen["vectors"],
        documents=gen["documents"],
        metadata_snapshot_checksum=gen["snapshot_summary"]["metadata_snapshot_checksum"],
        generation_duration_seconds=gen["generation_duration_seconds"],
        peak_memory_mb=gen["peak_memory_mb"],
    )
    register_in_process_artifact(art)
    monkeypatch.setenv("RECOMMENDATION_STRATEGY", "deterministic_test")

    cold_recs = get_recommendations(db_session, user.id, top_n=2)
    assert len(cold_recs) == 2
    assert cold_recs[0]["score"] == 0.0
    assert "Recently released movie" in cold_recs[0]["reason"]

    # Add 5-star rating on m1 (Blade Runner 2049) and verify semantic recommendations work
    db_session.add(Rating(user_id=user.id, movie_id=m1.id, rating=5))
    db_session.commit()

    sem_recs = get_recommendations(db_session, user.id, top_n=3)
    assert len(sem_recs) == 3
    recommended_ids = [r["id"] for r in sem_recs]
    assert str(m1.id) not in recommended_ids  # Seen-item exclusion

    # Now simulate missing cache -> must fall back to TF-IDF v1.1 without error and increment fallback_count
    invalidate_embedding_cache()
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", str(tmp_path / "nonexistent_dir"))
    monkeypatch.setenv("RECOMMENDATION_STRATEGY", "semantic_en")

    before_fallbacks = get_embedding_cache_stats()["fallback_count"]
    fallback_recs = get_recommendations(db_session, user.id, top_n=3)
    after_fallbacks = get_embedding_cache_stats()["fallback_count"]

    assert len(fallback_recs) == 3
    assert after_fallbacks == before_fallbacks + 1

    # Simulate stale cache (movie metadata_version bumped after enrichment) -> safe fallback to TF-IDF v1.1
    register_in_process_artifact(art)
    monkeypatch.setenv("RECOMMENDATION_STRATEGY", "deterministic_test")
    m2.metadata_version = 2
    db_session.commit()

    stale_recs = get_recommendations(db_session, user.id, top_n=3)
    assert len(stale_recs) == 3
    assert get_embedding_cache_stats()["fallback_count"] == after_fallbacks + 1


# ── 19: Offline Evaluation Adapter & Statistical Tests ────────────────────────

def test_offline_evaluation_adapter_and_paired_statistics(tmp_path: Path):
    """19. OfflineSemanticRecommender and evaluate_recommender compute valid Top-K metrics offline."""
    movies = {
        "1": MovieMetadata(movie_id="1", title="Sci-Fi Alpha", genres=["Sci-Fi"], tags=["space", "alien"]),
        "2": MovieMetadata(movie_id="2", title="Sci-Fi Beta", genres=["Sci-Fi"], tags=["space", "alien"]),
        "3": MovieMetadata(movie_id="3", title="Romance Gamma", genres=["Romance"], tags=["love", "wedding"]),
        "4": MovieMetadata(movie_id="4", title="Sci-Fi Delta", genres=["Sci-Fi"], tags=["space", "robot"]),
    }
    for m in movies.values():
        m.text_profile = f"{m.title} {m.title} {' '.join(m.genres)} {' '.join(m.tags)}"

    dataset = EvaluationDataset(
        movies=movies,
        train_by_user={
            "u1": [RatingEvent(user_id="u1", movie_id="1", rating=5.0, timestamp=100)],
            "u2": [RatingEvent(user_id="u2", movie_id="3", rating=5.0, timestamp=100)],
        },
        val_by_user={"u1": [], "u2": []},
        test_by_user={
            "u1": [RatingEvent(user_id="u1", movie_id="2", rating=4.5, timestamp=200)],
            "u2": [RatingEvent(user_id="u2", movie_id="4", rating=4.0, timestamp=200)],
        },
        raw_files_checksum="raw_test_sha",
        split_checksum="split_test_sha",
        total_ratings_count=4,
        users_count=2,
        movies_count=4,
    )

    cfg = SemanticModelConfig(
        algorithm_name="Test-Semantic",
        model_key="deterministic_test",
        k_values=(1, 2, 3),
    )
    recommender = OfflineSemanticRecommender(
        config=cfg,
        cache_dir=tmp_path,
        encoder=DeterministicHashEncoder(spec=DETERMINISTIC_TEST_SPEC),
    )
    result = evaluate_recommender(recommender, cfg, dataset)

    assert result.total_users_evaluated == 2
    assert result.users_with_relevant_items == 2
    assert "k_1" in result.aggregate_metrics["by_k"]
    # User u1 trained on Sci-Fi Alpha ("1") should rank Sci-Fi Beta ("2") or Delta ("4") at the top
    u1_row = next(r for r in result.per_user_rows if r.user_id == "u1")
    assert "1" not in u1_row.recommendations_top20  # Seen training item excluded
    assert u1_row.recommendations_top20[0] in ("2", "4")

    # Verify paired comparison helper
    paired = compute_extended_paired_comparison([0.1, 0.2, 0.3], [0.2, 0.3, 0.5])
    assert paired["mean_difference"] > 0
    assert paired["win_tie_loss"] == {"wins": 3, "ties": 0, "losses": 0}
    assert paired["evidence_status"] == "NOT ENOUGH EVIDENCE"  # N=3 < 30
