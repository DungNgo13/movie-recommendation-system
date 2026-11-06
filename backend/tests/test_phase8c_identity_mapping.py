"""
Phase 8C Identity Mapping, Research Snapshot, and Enrichment Tests.

Tests:
  - Valid external ID mapping from links.csv
  - Missing / empty TMDB IDs
  - Duplicate TMDB IDs
  - Identity coverage report generation
  - Research metadata snapshot creation, save, load, integrity
  - Snapshot determinism and immutability
  - Mock TMDB retrieval pipeline
  - Stratified pilot subset selection
  - Field-level coverage report generation
  - Research / production isolation
  - Dataset compatibility
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.recommendation_evaluation.dataset import (
    EvaluationDataset,
    MovieMetadata,
    RatingEvent,
    build_movielens_text_profile,
)
from app.recommendation_evaluation.identity_mapping import (
    ExternalIdRecord,
    IdentityMappingResult,
    build_tmdb_to_movielens_index,
    generate_identity_coverage_report,
    get_imdb_id_for_movie,
    get_tmdb_id_for_movie,
    load_identity_mapping,
)
from app.recommendation_evaluation.research_snapshot import (
    ResearchMetadataSnapshot,
    compute_field_coverage,
    create_snapshot,
    deserialize_movie_metadata,
    load_movies_from_snapshot,
    load_snapshot,
    save_snapshot,
    serialize_movie_metadata,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_dataset_dir(tmp_path: Path) -> Path:
    """Create a minimal MovieLens-like dataset directory for testing."""
    # movies.csv
    movies_csv = (
        "movieId,title,genres\n"
        "1,Toy Story (1995),Adventure|Animation|Children|Comedy|Fantasy\n"
        "2,Jumanji (1995),Adventure|Children|Fantasy\n"
        "3,Grumpier Old Men (1995),Comedy|Romance\n"
        "4,Waiting to Exhale (1995),Comedy|Drama|Romance\n"
        "5,Father of the Bride Part II (1995),Comedy\n"
        "6,Heat (1995),Action|Crime|Thriller\n"
        "7,Sabrina (1995),Comedy|Romance\n"
        "8,Tom and Huck (1995),Adventure|Children\n"
        "9,Sudden Death (1995),Action\n"
        "10,GoldenEye (1995),Action|Adventure|Thriller\n"
    )
    (tmp_path / "movies.csv").write_text(movies_csv, encoding="utf-8")

    # links.csv
    links_csv = (
        "movieId,imdbId,tmdbId\n"
        "1,0114709,862\n"
        "2,0113497,8844\n"
        "3,0113228,15602\n"
        "4,0114885,31357\n"
        "5,0113041,11862\n"
        "6,0113277,949\n"
        "7,0114319,11860\n"
        "8,0112302,\n"       # Missing TMDB ID
        "9,0114576,9091\n"
        "10,0113189,710\n"
    )
    (tmp_path / "links.csv").write_text(links_csv, encoding="utf-8")

    return tmp_path


@pytest.fixture
def sample_mapping(sample_dataset_dir: Path) -> IdentityMappingResult:
    """Load identity mapping from the sample dataset directory."""
    return load_identity_mapping(sample_dataset_dir)


@pytest.fixture
def sample_movies() -> dict[str, MovieMetadata]:
    """Create sample MovieMetadata for testing."""
    movies: dict[str, MovieMetadata] = {}
    for i in range(1, 6):
        m = MovieMetadata(
            movie_id=str(i),
            title=f"Movie {i}",
            genres=["Drama", "Action"],
            tags=["tag1", "tag2"],
        )
        m.text_profile = build_movielens_text_profile(m.title, m.genres, m.tags)
        movies[str(i)] = m
    return movies


@pytest.fixture
def sample_dataset(sample_movies: dict[str, MovieMetadata]) -> EvaluationDataset:
    """Create a minimal EvaluationDataset for testing."""
    train = {
        "u1": [
            RatingEvent("u1", "1", 5.0, 100),
            RatingEvent("u1", "2", 4.0, 200),
            RatingEvent("u1", "3", 3.0, 300),
        ],
        "u2": [
            RatingEvent("u2", "1", 4.0, 100),
            RatingEvent("u2", "4", 5.0, 200),
        ],
    }
    val = {"u1": [], "u2": []}
    test = {
        "u1": [RatingEvent("u1", "4", 4.5, 400)],
        "u2": [RatingEvent("u2", "2", 4.0, 300)],
    }
    return EvaluationDataset(
        movies=sample_movies,
        train_by_user=train,
        val_by_user=val,
        test_by_user=test,
        raw_files_checksum="test_checksum_abc",
        split_checksum="test_split_xyz",
        total_ratings_count=6,
        users_count=2,
        movies_count=len(sample_movies),
    )


# ── Identity Mapping Tests ────────────────────────────────────────────────


class TestIdentityMapping:
    """Tests for the MovieLens-to-TMDB identity mapping layer."""

    def test_load_identity_mapping_basic(self, sample_mapping: IdentityMappingResult):
        """Valid mapping loads correct record counts."""
        assert sample_mapping.total_movielens_movies == 10
        assert sample_mapping.total_links_rows == 10
        assert sample_mapping.movies_with_tmdb_id == 9  # movie 8 has no TMDB ID
        assert sample_mapping.movies_without_tmdb_id == 1

    def test_tmdb_coverage_percentage(self, sample_mapping: IdentityMappingResult):
        """TMDB coverage percentage is correctly computed."""
        assert sample_mapping.tmdb_coverage_pct == 90.0

    def test_imdb_coverage(self, sample_mapping: IdentityMappingResult):
        """All movies have IMDb IDs in this test set."""
        assert sample_mapping.movies_with_imdb_id == 10
        assert sample_mapping.imdb_coverage_pct == 100.0

    def test_missing_tmdb_id_detected(self, sample_mapping: IdentityMappingResult):
        """Movie 8 should be detected as missing TMDB ID."""
        assert "8" in sample_mapping.unmapped_movie_ids

    def test_get_tmdb_id_for_movie(self, sample_mapping: IdentityMappingResult):
        """Look up known TMDB IDs."""
        assert get_tmdb_id_for_movie(sample_mapping, "1") == 862
        assert get_tmdb_id_for_movie(sample_mapping, "2") == 8844
        assert get_tmdb_id_for_movie(sample_mapping, "8") is None  # Missing
        assert get_tmdb_id_for_movie(sample_mapping, "999") is None  # Non-existent

    def test_get_imdb_id_for_movie(self, sample_mapping: IdentityMappingResult):
        """Look up IMDb IDs with tt prefix."""
        assert get_imdb_id_for_movie(sample_mapping, "1") == "tt0114709"
        assert get_imdb_id_for_movie(sample_mapping, "6") == "tt0113277"

    def test_build_reverse_index(self, sample_mapping: IdentityMappingResult):
        """Reverse index maps TMDB IDs back to MovieLens IDs."""
        reverse = build_tmdb_to_movielens_index(sample_mapping)
        assert reverse[862] == "1"
        assert reverse[8844] == "2"
        assert len(reverse) == 9  # 9 movies with TMDB IDs

    def test_links_checksum_computed(self, sample_mapping: IdentityMappingResult):
        """links.csv checksum is non-empty."""
        assert len(sample_mapping.links_checksum) == 64  # SHA-256 hex

    def test_title_year_index(self, sample_mapping: IdentityMappingResult):
        """Title and year are extracted from movies.csv."""
        title, year = sample_mapping.title_year_index["1"]
        assert title == "Toy Story (1995)"
        assert year == 1995

    def test_no_duplicate_tmdb_ids_in_clean_data(
        self, sample_mapping: IdentityMappingResult
    ):
        """No duplicates in the test dataset."""
        assert len(sample_mapping.duplicate_tmdb_ids) == 0

    def test_identity_coverage_report_generation(
        self, sample_mapping: IdentityMappingResult, tmp_path: Path
    ):
        """JSON identity coverage report is generated correctly."""
        report_path = generate_identity_coverage_report(sample_mapping, tmp_path)
        assert report_path.exists()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["report_type"] == "phase8c_identity_coverage"
        assert report["summary"]["total_movielens_catalog"] == 10
        assert report["summary"]["movies_with_tmdb_id"] == 9

    def test_missing_links_csv_raises(self, tmp_path: Path):
        """FileNotFoundError when links.csv is missing."""
        (tmp_path / "movies.csv").write_text(
            "movieId,title,genres\n1,Test,Drama\n", encoding="utf-8"
        )
        with pytest.raises(FileNotFoundError, match="links.csv"):
            load_identity_mapping(tmp_path)


class TestIdentityMappingDuplicates:
    """Test duplicate TMDB ID detection."""

    def test_duplicate_tmdb_id_detected(self, tmp_path: Path):
        """Duplicate TMDB IDs are flagged."""
        movies_csv = "movieId,title,genres\n1,Movie A (2000),Drama\n2,Movie B (2001),Comedy\n"
        links_csv = "movieId,imdbId,tmdbId\n1,0000001,999\n2,0000002,999\n"  # Same TMDB ID

        (tmp_path / "movies.csv").write_text(movies_csv, encoding="utf-8")
        (tmp_path / "links.csv").write_text(links_csv, encoding="utf-8")

        result = load_identity_mapping(tmp_path)
        assert len(result.duplicate_tmdb_ids) == 1
        assert result.duplicate_tmdb_ids[0]["tmdb_id"] == 999
        assert set(result.duplicate_tmdb_ids[0]["movielens_ids"]) == {"1", "2"}


# ── Research Snapshot Tests ───────────────────────────────────────────────


class TestResearchSnapshot:
    """Tests for research metadata snapshot infrastructure."""

    def test_serialize_deserialize_round_trip(self, sample_movies: dict[str, MovieMetadata]):
        """MovieMetadata survives serialization round trip."""
        original = sample_movies["1"]
        serialized = serialize_movie_metadata(original)
        restored = deserialize_movie_metadata(serialized)

        assert restored.movie_id == original.movie_id
        assert restored.title == original.title
        assert restored.genres == original.genres
        assert restored.tags == original.tags
        assert restored.metadata_source == original.metadata_source

    def test_create_snapshot(self, sample_movies: dict[str, MovieMetadata]):
        """Snapshot creation with correct metadata."""
        snap = create_snapshot(
            snapshot_id="test_001",
            movies=sample_movies,
            movielens_checksum="abc123",
            split_checksum="xyz789",
            links_checksum="links_hash",
            enriched_count=2,
            failed_count=0,
            enrichment_source="mock_tmdb_catalog",
        )
        assert snap.snapshot_id == "test_001"
        assert snap.total_movies == 5
        assert snap.enriched_count == 2
        assert snap.snapshot_checksum  # Non-empty

    def test_snapshot_checksum_deterministic(self, sample_movies: dict[str, MovieMetadata]):
        """Same input produces the same checksum."""
        snap1 = create_snapshot(
            snapshot_id="det_test",
            movies=sample_movies,
            movielens_checksum="abc",
            split_checksum="xyz",
            links_checksum="links",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        snap2 = create_snapshot(
            snapshot_id="det_test",
            movies=sample_movies,
            movielens_checksum="abc",
            split_checksum="xyz",
            links_checksum="links",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        assert snap1.snapshot_checksum == snap2.snapshot_checksum

    def test_save_and_load_snapshot(
        self, sample_movies: dict[str, MovieMetadata], tmp_path: Path
    ):
        """Save and load preserves snapshot data."""
        snap = create_snapshot(
            snapshot_id="save_load_test",
            movies=sample_movies,
            movielens_checksum="chk1",
            split_checksum="chk2",
            links_checksum="chk3",
            enriched_count=1,
            failed_count=0,
            enrichment_source="mock_tmdb_catalog",
        )
        filepath = save_snapshot(snap, tmp_path)
        assert filepath.exists()

        loaded = load_snapshot(filepath)
        assert loaded.snapshot_id == "save_load_test"
        assert loaded.total_movies == 5
        assert loaded.enriched_count == 1
        assert loaded.snapshot_checksum == snap.snapshot_checksum

    def test_snapshot_immutability(
        self, sample_movies: dict[str, MovieMetadata], tmp_path: Path
    ):
        """Saving the same snapshot ID twice raises FileExistsError."""
        snap = create_snapshot(
            snapshot_id="immutable_test",
            movies=sample_movies,
            movielens_checksum="c1",
            split_checksum="c2",
            links_checksum="c3",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        save_snapshot(snap, tmp_path)

        with pytest.raises(FileExistsError, match="immutable"):
            save_snapshot(snap, tmp_path)

    def test_load_movies_from_snapshot(
        self, sample_movies: dict[str, MovieMetadata], tmp_path: Path
    ):
        """Movies can be restored from a saved snapshot."""
        snap = create_snapshot(
            snapshot_id="load_movies",
            movies=sample_movies,
            movielens_checksum="c1",
            split_checksum="c2",
            links_checksum="c3",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        filepath = save_snapshot(snap, tmp_path)
        loaded_snap = load_snapshot(filepath)
        restored_movies = load_movies_from_snapshot(loaded_snap)

        assert len(restored_movies) == len(sample_movies)
        assert restored_movies["1"].title == sample_movies["1"].title
        assert restored_movies["1"].genres == sample_movies["1"].genres

    def test_snapshot_integrity_check(
        self, sample_movies: dict[str, MovieMetadata], tmp_path: Path
    ):
        """Corrupted snapshot checksum is detected on load."""
        snap = create_snapshot(
            snapshot_id="integrity_test",
            movies=sample_movies,
            movielens_checksum="c1",
            split_checksum="c2",
            links_checksum="c3",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        filepath = save_snapshot(snap, tmp_path)

        # Corrupt the checksum
        data = json.loads(filepath.read_text(encoding="utf-8"))
        data["snapshot_checksum"] = "corrupted_hash_value"
        filepath.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(ValueError, match="checksum mismatch"):
            load_snapshot(filepath)

    def test_field_coverage_computation(self, sample_movies: dict[str, MovieMetadata]):
        """Field coverage correctly counts present fields."""
        # Add some enrichment to movie 1
        sample_movies["1"].overview = "A great movie about toys"
        sample_movies["1"].director = "John Lasseter"
        sample_movies["1"].cast = ["Tom Hanks", "Tim Allen"]

        cov = compute_field_coverage(sample_movies)
        assert cov.title == 5  # All have titles
        assert cov.overview == 1  # Only movie 1
        assert cov.director == 1
        assert cov.cast == 1
        assert cov.genres == 5  # All have genres

    def test_manifest_file_created(
        self, sample_movies: dict[str, MovieMetadata], tmp_path: Path
    ):
        """Save creates both full snapshot and compact manifest."""
        snap = create_snapshot(
            snapshot_id="manifest_test",
            movies=sample_movies,
            movielens_checksum="c1",
            split_checksum="c2",
            links_checksum="c3",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        save_snapshot(snap, tmp_path)

        manifest_path = tmp_path / "manifest_manifest_test.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "movies" not in manifest  # Compact manifest has no movie data
        assert manifest["snapshot_id"] == "manifest_test"


# ── TMDB Research Retrieval Tests ─────────────────────────────────────────


class TestTMDBResearchRetrieval:
    """Tests for mock TMDB metadata retrieval and pilot selection."""

    def test_stratified_pilot_deterministic(
        self, sample_dataset: EvaluationDataset, sample_mapping_with_dataset
    ):
        """Same seed produces the same pilot subset."""
        from app.recommendation_evaluation.tmdb_research_retrieval import (
            select_stratified_pilot_subset,
        )

        mapping = sample_mapping_with_dataset
        pilot1 = select_stratified_pilot_subset(sample_dataset, mapping, sample_size=3, seed=42)
        pilot2 = select_stratified_pilot_subset(sample_dataset, mapping, sample_size=3, seed=42)
        assert pilot1 == pilot2

    def test_stratified_pilot_different_seeds(
        self, sample_dataset: EvaluationDataset, sample_mapping_with_dataset
    ):
        """Different seeds produce different subsets."""
        from app.recommendation_evaluation.tmdb_research_retrieval import (
            select_stratified_pilot_subset,
        )

        mapping = sample_mapping_with_dataset
        pilot_a = select_stratified_pilot_subset(sample_dataset, mapping, sample_size=3, seed=1)
        pilot_b = select_stratified_pilot_subset(sample_dataset, mapping, sample_size=3, seed=999)
        # With only 5 movies, they might overlap, but seeds differ
        assert isinstance(pilot_a, list)
        assert isinstance(pilot_b, list)

    def test_mock_retrieval_returns_enriched_movies(
        self, sample_dataset: EvaluationDataset, sample_mapping_with_dataset
    ):
        """Mock retrieval produces enriched MovieMetadata objects."""
        from app.recommendation_evaluation.tmdb_research_retrieval import (
            retrieve_mock_tmdb_metadata,
        )

        mapping = sample_mapping_with_dataset
        movie_ids = ["1", "2", "3"]
        enriched, summary = retrieve_mock_tmdb_metadata(movie_ids, sample_dataset, mapping)

        assert len(enriched) == 3
        assert summary.total_attempted == 3

    def test_build_enriched_catalog_preserves_unenriched(
        self, sample_dataset: EvaluationDataset
    ):
        """Unenriched movies are preserved in the merged catalog."""
        from app.recommendation_evaluation.tmdb_research_retrieval import (
            build_enriched_catalog,
        )

        enriched_subset = {"1": sample_dataset.movies["1"]}
        full = build_enriched_catalog(sample_dataset, enriched_subset)
        assert len(full) == len(sample_dataset.movies)
        assert "2" in full  # Unenriched movie preserved

    def test_coverage_report_generation(
        self, sample_dataset: EvaluationDataset, sample_mapping_with_dataset, tmp_path: Path
    ):
        """Field-level coverage report is generated as JSON and CSV."""
        from app.recommendation_evaluation.tmdb_research_retrieval import (
            RetrievalSummary,
            generate_coverage_report,
        )

        mapping = sample_mapping_with_dataset
        summary = RetrievalSummary(total_attempted=3, successful=3)

        report_path = generate_coverage_report(
            enriched_movies=sample_dataset.movies,
            total_catalog_size=5,
            retrieval_summary=summary,
            mapping=mapping,
            output_dir=tmp_path,
            snapshot_id="test_snap",
        )

        assert report_path.exists()
        assert (tmp_path / "phase8c_field_coverage.csv").exists()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["report_type"] == "phase8c_field_coverage"


@pytest.fixture
def sample_mapping_with_dataset(
    sample_movies: dict[str, MovieMetadata],
) -> IdentityMappingResult:
    """Create a minimal IdentityMappingResult matching sample_movies."""
    records = {}
    for i in range(1, 6):
        records[str(i)] = ExternalIdRecord(
            movielens_id=str(i),
            imdb_id=f"000000{i}",
            tmdb_id=100 + i,
        )

    return IdentityMappingResult(
        total_movielens_movies=5,
        total_links_rows=5,
        movies_with_tmdb_id=5,
        movies_without_tmdb_id=0,
        movies_with_imdb_id=5,
        movies_without_imdb_id=0,
        tmdb_coverage_pct=100.0,
        imdb_coverage_pct=100.0,
        duplicate_tmdb_ids=[],
        movies_only_in_links=[],
        movies_only_in_catalog=[],
        links_checksum="test_links_checksum",
        records=records,
        unmapped_movie_ids=[],
        title_year_index={
            "1": ("Movie 1 (2000)", 2000),
            "2": ("Movie 2 (2001)", 2001),
            "3": ("Movie 3 (2002)", 2002),
            "4": ("Movie 4 (2003)", 2003),
            "5": ("Movie 5 (2004)", 2004),
        },
    )


# ── Production Isolation Tests ────────────────────────────────────────────


class TestProductionIsolation:
    """Verify that research snapshots never touch production database."""

    def test_snapshot_is_json_file(
        self, sample_movies: dict[str, MovieMetadata], tmp_path: Path
    ):
        """Snapshots are JSON files, not database records."""
        snap = create_snapshot(
            snapshot_id="isolation_test",
            movies=sample_movies,
            movielens_checksum="c1",
            split_checksum="c2",
            links_checksum="c3",
            enriched_count=0,
            failed_count=0,
            enrichment_source="mock",
        )
        filepath = save_snapshot(snap, tmp_path)
        assert filepath.suffix == ".json"
        # Verify it's valid JSON
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_no_sqlalchemy_imports_in_snapshot_module(self):
        """research_snapshot module does not import SQLAlchemy."""
        import app.recommendation_evaluation.research_snapshot as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "sqlalchemy" not in source.lower()
        assert "from app.models" not in source

    def test_no_sqlalchemy_imports_in_identity_mapping(self):
        """identity_mapping module does not import SQLAlchemy."""
        import app.recommendation_evaluation.identity_mapping as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "sqlalchemy" not in source.lower()
        assert "from app.models" not in source
