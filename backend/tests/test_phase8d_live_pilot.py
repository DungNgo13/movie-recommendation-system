"""Tests for Phase 8D controlled live TMDB pilot pipeline.

Tests cover:
- Phase8DPilotConfig creation and authorization gate logic
- Deterministic pilot movie selection
- Authorization gate checking
- Title matching logic
- Year matching logic
- Checkpoint save/load round-trip
- Pilot manifest generation
- Quality report generation
- Full catalog estimation
- Dry-run execution producing NOT_RUN records
- Budget enforcement
- No production database imports
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Phase8DPilotConfig
# ---------------------------------------------------------------------------


class TestPhase8DPilotConfig:
    """Tests for Phase8DPilotConfig.from_args authorization gate."""

    def test_from_args_default_dry_run(self):
        """Default args produce dry-run config."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            config = Phase8DPilotConfig.from_args()
            assert config.dry_run is True
            assert config.live_authorized is False

    def test_from_args_live_flag_without_env(self):
        """Live flag without env var still results in dry-run."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            config = Phase8DPilotConfig.from_args(live=True)
            assert config.dry_run is True
            assert config.live_authorized is False

    def test_from_args_env_without_live_flag(self):
        """Env var without live flag still results in dry-run."""
        with patch.dict(os.environ, {"PHASE8D_LIVE_AUTHORIZED": "true"}, clear=False):
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            config = Phase8DPilotConfig.from_args(live=False)
            assert config.dry_run is True

    def test_from_args_both_live_flag_and_env(self):
        """Both live flag AND env var produce live config."""
        with patch.dict(os.environ, {"PHASE8D_LIVE_AUTHORIZED": "true"}, clear=False):
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            config = Phase8DPilotConfig.from_args(live=True)
            assert config.dry_run is False
            assert config.live_authorized is True

    def test_budget_clamping_lower(self):
        """Budget below 1 is clamped to 1."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            config = Phase8DPilotConfig.from_args(request_budget=0)
            assert config.request_budget == 1

    def test_budget_clamping_upper(self):
        """Budget above approved 74 cap (including 94 or 120) is clamped to 74."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            assert Phase8DPilotConfig.from_args(request_budget=94).request_budget == 74
            assert Phase8DPilotConfig.from_args(request_budget=120).request_budget == 74
            assert Phase8DPilotConfig.from_args(request_budget=9999).request_budget == 74

    def test_budget_within_range(self):
        """Budget within valid range [1, 74] is preserved."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            from app.recommendation_evaluation.phase8d_live_pilot import Phase8DPilotConfig

            config = Phase8DPilotConfig.from_args(request_budget=50)
            assert config.request_budget == 50

    def test_default_constants(self):
        """Default config values match module constants."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            PHASE8D_DEFAULT_PILOT_SIZE,
            PHASE8D_DEFAULT_REQUEST_BUDGET,
            PHASE8D_DEFAULT_SEED,
            Phase8DPilotConfig,
        )

        config = Phase8DPilotConfig()
        assert config.pilot_size == PHASE8D_DEFAULT_PILOT_SIZE
        assert config.seed == PHASE8D_DEFAULT_SEED
        assert config.request_budget == PHASE8D_DEFAULT_REQUEST_BUDGET


# ---------------------------------------------------------------------------
# Title matching
# ---------------------------------------------------------------------------


class TestTitleMatch:
    """Tests for _check_title_match identity verification."""

    def test_exact_match(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert _check_title_match("Toy Story (1995)", "Toy Story", "") is True

    def test_substring_match_tmdb_longer(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert (
            _check_title_match(
                "Star Wars: Episode IV (1977)",
                "Star Wars: Episode IV - A New Hope",
                "",
            )
            is True
        )

    def test_original_title_match(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert (
            _check_title_match("Seven Samurai (1954)", "The Seven Samurai", "七人の侍")
            is True
        )

    def test_no_match(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert (
            _check_title_match("Toy Story (1995)", "The Godfather", "The Godfather")
            is False
        )

    def test_the_prefix_handling(self):
        """Removing 'The' prefix enables match between 'Matrix' and 'Matrix'."""
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        # "the matrix" as substring match
        assert _check_title_match("The Matrix (1999)", "The Matrix", "") is True

    def test_empty_tmdb_titles(self):
        """Empty TMDB titles must NOT match (prevents false positive on empty string)."""
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert _check_title_match("Toy Story (1995)", "", "") is False

    def test_trailing_article_movielens_format(self):
        """MovieLens 'Title, The (Year)' matches TMDB 'The Title'."""
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert (
            _check_title_match(
                "Wolf of Wall Street, The (2013)",
                "The Wolf of Wall Street",
                "The Wolf of Wall Street",
            )
            is True
        )

    def test_case_insensitive(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_title_match

        assert _check_title_match("TOY STORY (1995)", "toy story", "") is True


# ---------------------------------------------------------------------------
# Year matching
# ---------------------------------------------------------------------------


class TestYearMatch:
    """Tests for _check_year_match identity verification."""

    def test_exact_year(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(1995, "1995-11-22") is True

    def test_one_year_tolerance_earlier(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(1994, "1995-01-01") is True

    def test_one_year_tolerance_later(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(1996, "1995-01-01") is True

    def test_beyond_tolerance(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(1990, "1995-01-01") is False

    def test_none_year_is_ok(self):
        """None movielens year cannot be verified, so passes."""
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(None, "1995-01-01") is True

    def test_empty_release_date_is_ok(self):
        """Empty TMDB release date cannot be verified, so passes."""
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(1995, "") is True

    def test_malformed_release_date(self):
        """Malformed date string is treated as OK (cannot verify)."""
        from app.recommendation_evaluation.phase8d_live_pilot import _check_year_match

        assert _check_year_match(1995, "not-a-date") is True


# ---------------------------------------------------------------------------
# Checkpoint round-trip
# ---------------------------------------------------------------------------


class TestCheckpoint:
    """Tests for checkpoint save/load round-trip."""

    def test_save_and_load(self, tmp_path):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            LiveRetrievalRecord,
            _load_checkpoint,
            _save_checkpoint,
        )

        record = LiveRetrievalRecord(
            movielens_id="1",
            tmdb_id=862,
            imdb_id="tt0114709",
            movielens_title="Toy Story (1995)",
            movielens_year=1995,
            tmdb_title="Toy Story",
            tmdb_original_title="Toy Story",
            tmdb_release_date="1995-10-30",
            status="success",
            verification_status="LIVE_VERIFIED",
            title_match=True,
            year_match=True,
            fields_retrieved=["overview", "genres"],
            fields_missing=[],
            request_count=2,
            latency_ms=150.0,
        )
        _save_checkpoint(tmp_path, "1", record, ["1"])
        loaded = _load_checkpoint(tmp_path)
        assert "1" in loaded
        assert len(loaded) == 1

    def test_load_empty_dir(self, tmp_path):
        from app.recommendation_evaluation.phase8d_live_pilot import _load_checkpoint

        loaded = _load_checkpoint(tmp_path)
        assert loaded == set()

    def test_multiple_checkpoints(self, tmp_path):
        """Saving multiple checkpoints preserves all completed IDs."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            LiveRetrievalRecord,
            _load_checkpoint,
            _save_checkpoint,
        )

        record = LiveRetrievalRecord(
            movielens_id="1",
            tmdb_id=862,
            imdb_id="tt0114709",
            movielens_title="Toy Story (1995)",
            movielens_year=1995,
            tmdb_title="Toy Story",
            tmdb_original_title="Toy Story",
            tmdb_release_date="1995-10-30",
            status="success",
            verification_status="LIVE_VERIFIED",
            title_match=True,
            year_match=True,
            fields_retrieved=["overview"],
            fields_missing=[],
            request_count=2,
            latency_ms=150.0,
        )
        _save_checkpoint(tmp_path, "1", record, ["1"])
        _save_checkpoint(tmp_path, "2", record, ["1", "2"])
        loaded = _load_checkpoint(tmp_path)
        assert loaded == {"1", "2"}

    def test_checkpoint_file_content(self, tmp_path):
        """Checkpoint JSON file has correct structure."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            LiveRetrievalRecord,
            _save_checkpoint,
        )

        record = LiveRetrievalRecord(
            movielens_id="1",
            tmdb_id=862,
            imdb_id="tt0114709",
            movielens_title="Toy Story (1995)",
            movielens_year=1995,
            tmdb_title="Toy Story",
            tmdb_original_title="Toy Story",
            tmdb_release_date="1995-10-30",
            status="success",
            verification_status="LIVE_VERIFIED",
            title_match=True,
            year_match=True,
            fields_retrieved=[],
            fields_missing=[],
            request_count=1,
            latency_ms=100.0,
        )
        _save_checkpoint(tmp_path, "1", record, ["1"])
        cp_data = json.loads((tmp_path / "checkpoint.json").read_text())
        assert cp_data["last_movie_id"] == "1"
        assert cp_data["completed_count"] == 1
        assert cp_data["completed_ids"] == ["1"]
        assert "timestamp" in cp_data


# ---------------------------------------------------------------------------
# Authorization gate
# ---------------------------------------------------------------------------


class TestAuthorizationGate:
    """Tests for check_authorization_gate."""

    def test_blocked_gate(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            check_authorization_gate,
        )

        config = Phase8DPilotConfig(dry_run=True, live_authorized=False)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            os.environ.pop("TMDB_ENABLE_LIVE_REQUESTS", None)
            os.environ.pop("TMDB_API_READ_ACCESS_TOKEN", None)
            gate = check_authorization_gate(config)
            assert gate["gate_status"] == "BLOCKED"
            assert gate["authorization_granted"] is False

    def test_authorized_gate(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            check_authorization_gate,
        )

        config = Phase8DPilotConfig(dry_run=False, live_authorized=True)
        with patch.dict(
            os.environ,
            {
                "PHASE8D_LIVE_AUTHORIZED": "true",
                "TMDB_ENABLE_LIVE_REQUESTS": "true",
                "TMDB_API_READ_ACCESS_TOKEN": "test_token",
            },
            clear=False,
        ):
            gate = check_authorization_gate(config)
            assert gate["gate_status"] == "AUTHORIZED"
            assert gate["authorization_granted"] is True

    def test_gate_message_blocked(self):
        """Blocked gate includes helpful message."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            check_authorization_gate,
        )

        config = Phase8DPilotConfig(dry_run=True, live_authorized=False)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            os.environ.pop("TMDB_ENABLE_LIVE_REQUESTS", None)
            os.environ.pop("TMDB_API_READ_ACCESS_TOKEN", None)
            gate = check_authorization_gate(config)
            assert "NOT authorized" in gate["message"]
            assert "PHASE8D_LIVE_AUTHORIZED" in gate["message"]

    def test_gate_detects_token_presence(self):
        """Gate detects whether TMDB API token is present."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            check_authorization_gate,
        )

        config = Phase8DPilotConfig(dry_run=True, live_authorized=False)
        with patch.dict(
            os.environ,
            {"TMDB_API_READ_ACCESS_TOKEN": "some_token"},
            clear=False,
        ):
            os.environ.pop("PHASE8D_LIVE_AUTHORIZED", None)
            os.environ.pop("TMDB_ENABLE_LIVE_REQUESTS", None)
            gate = check_authorization_gate(config)
            assert gate["api_token_present"] is True


# ---------------------------------------------------------------------------
# Dry-run execution
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for dry-run mode producing NOT_RUN records."""

    @pytest.fixture
    def mock_dataset(self):
        """Create a minimal mock dataset."""
        dataset = MagicMock()
        movie1 = MagicMock()
        movie1.title = "Toy Story (1995)"
        movie1.genres = ["Animation"]
        movie1.tags = ["pixar"]
        movie2 = MagicMock()
        movie2.title = "Jumanji (1995)"
        movie2.genres = ["Adventure"]
        movie2.tags = []
        dataset.movies = {"1": movie1, "2": movie2}
        dataset.train_by_user = {}
        dataset.val_by_user = {}
        dataset.test_by_user = {}
        return dataset

    @pytest.fixture
    def mock_mapping(self):
        """Create a minimal mock identity mapping."""
        mapping = MagicMock()
        mapping.tmdb_lookup = {"1": 862, "2": 8844}
        mapping.imdb_lookup = {"1": "0114709", "2": "0113497"}
        mapping.title_year_index = {
            "1": ("Toy Story", 1995),
            "2": ("Jumanji", 1995),
        }
        return mapping

    def test_dry_run_produces_not_run_records(
        self, tmp_path, mock_dataset, mock_mapping
    ):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            run_live_pilot,
        )

        config = Phase8DPilotConfig(
            dry_run=True, live_authorized=False, request_budget=120
        )

        with (
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie"
            ) as mock_tmdb,
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie"
            ) as mock_imdb,
        ):
            mock_tmdb.side_effect = lambda m, mid: m.tmdb_lookup.get(mid)
            mock_imdb.side_effect = lambda m, mid: m.imdb_lookup.get(mid)

            summary = run_live_pilot(
                ["1", "2"], mock_dataset, mock_mapping, config, tmp_path
            )

        assert summary.is_live is False
        assert summary.verification_mode == "NOT_RUN"
        assert summary.total_attempted == 2
        assert len(summary.records) == 2
        for record in summary.records:
            assert record.verification_status == "NOT_RUN"
            assert record.status == "not_run"
            assert record.request_count == 0

    def test_dry_run_creates_checkpoint_dir(self, tmp_path, mock_dataset, mock_mapping):
        """Dry-run still creates the checkpoint directory."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            run_live_pilot,
        )

        config = Phase8DPilotConfig(dry_run=True, live_authorized=False)

        with (
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                return_value=862,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                return_value="0114709",
            ),
        ):
            run_live_pilot(["1"], mock_dataset, mock_mapping, config, tmp_path)

        assert (tmp_path / "checkpoint").is_dir()

    def test_dry_run_fields_missing_all(self, tmp_path, mock_dataset, mock_mapping):
        """Dry-run records have fields_missing=['all']."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            run_live_pilot,
        )

        config = Phase8DPilotConfig(dry_run=True, live_authorized=False)

        with (
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                return_value=862,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                return_value="0114709",
            ),
        ):
            summary = run_live_pilot(
                ["1"], mock_dataset, mock_mapping, config, tmp_path
            )

        assert summary.records[0].fields_missing == ["all"]
        assert summary.records[0].fields_retrieved == []


# ---------------------------------------------------------------------------
# Production isolation
# ---------------------------------------------------------------------------


class TestProductionIsolation:
    """Ensure Phase 8D has no production database dependencies."""

    def test_no_sqlalchemy_in_phase8d(self):
        """Phase 8D module must not import SQLAlchemy (no production DB dependency)."""
        source_path = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "recommendation_evaluation"
            / "phase8d_live_pilot.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert (
            "sqlalchemy" not in source.lower()
        ), "phase8d_live_pilot.py must not import SQLAlchemy"
        assert (
            "from ..models" not in source
        ), "phase8d_live_pilot.py must not import from models"
        assert (
            "from ..database" not in source
        ), "phase8d_live_pilot.py must not import database"

    def test_no_secrets_in_constants(self):
        """No hardcoded tokens or secrets in module."""
        source_path = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "recommendation_evaluation"
            / "phase8d_live_pilot.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "eyJ" not in source, "No JWT-like tokens in source"

    def test_no_direct_database_imports(self):
        """No direct database session or engine imports."""
        source_path = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "recommendation_evaluation"
            / "phase8d_live_pilot.py"
        )
        source = source_path.read_text(encoding="utf-8")
        assert "SessionLocal" not in source
        assert "create_engine" not in source
        assert "get_db" not in source


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


class TestManifestGeneration:
    """Tests for generate_pilot_manifest."""

    def test_generate_creates_json_and_csv(self, tmp_path):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            generate_pilot_manifest,
        )

        dataset = MagicMock()
        movie1 = MagicMock()
        movie1.title = "Toy Story (1995)"
        movie1.genres = ["Animation"]
        movie1.tags = ["pixar"]
        dataset.movies = {"1": movie1}
        dataset.train_by_user = {}
        dataset.val_by_user = {}
        dataset.test_by_user = {}

        mapping = MagicMock()
        mapping.title_year_index = {"1": ("Toy Story", 1995)}

        with (
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                return_value=862,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                return_value="0114709",
            ),
        ):
            result = generate_pilot_manifest(
                ["1"], dataset, mapping, {"seed": 8042}, tmp_path
            )

        assert result.exists()
        assert (tmp_path / "phase8d_pilot_manifest.json").exists()
        assert (tmp_path / "phase8d_pilot_manifest.csv").exists()

        manifest = json.loads(
            (tmp_path / "phase8d_pilot_manifest.json").read_text()
        )
        assert manifest["manifest_type"] == "phase8d_pilot_manifest"
        assert manifest["pilot_size"] == 1
        assert len(manifest["movies"]) == 1

    def test_manifest_movie_details(self, tmp_path):
        """Manifest movie entries contain required fields."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            generate_pilot_manifest,
        )

        dataset = MagicMock()
        movie1 = MagicMock()
        movie1.title = "Toy Story (1995)"
        movie1.genres = ["Animation", "Comedy"]
        movie1.tags = ["pixar", "fun"]
        dataset.movies = {"1": movie1}
        dataset.train_by_user = {}
        dataset.val_by_user = {}
        dataset.test_by_user = {}

        mapping = MagicMock()
        mapping.title_year_index = {"1": ("Toy Story", 1995)}

        with (
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                return_value=862,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                return_value="0114709",
            ),
        ):
            generate_pilot_manifest(
                ["1"], dataset, mapping, {"seed": 8042}, tmp_path
            )

        manifest = json.loads(
            (tmp_path / "phase8d_pilot_manifest.json").read_text()
        )
        movie = manifest["movies"][0]
        assert movie["movielens_id"] == "1"
        assert movie["tmdb_id"] == 862
        assert movie["has_tmdb_id"] is True
        assert movie["tag_count"] == 2

    def test_manifest_estimated_requests(self, tmp_path):
        """Manifest estimates 2 requests per movie with TMDB ID."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            generate_pilot_manifest,
        )

        dataset = MagicMock()
        movie1 = MagicMock()
        movie1.title = "Toy Story (1995)"
        movie1.genres = ["Animation"]
        movie1.tags = []
        movie2 = MagicMock()
        movie2.title = "Jumanji (1995)"
        movie2.genres = ["Adventure"]
        movie2.tags = []
        dataset.movies = {"1": movie1, "2": movie2}
        dataset.train_by_user = {}
        dataset.val_by_user = {}
        dataset.test_by_user = {}

        mapping = MagicMock()
        mapping.title_year_index = {
            "1": ("Toy Story", 1995),
            "2": ("Jumanji", 1995),
        }

        with (
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                return_value=862,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                return_value="0114709",
            ),
        ):
            generate_pilot_manifest(
                ["1", "2"], dataset, mapping, {"seed": 8042}, tmp_path
            )

        manifest = json.loads(
            (tmp_path / "phase8d_pilot_manifest.json").read_text()
        )
        assert manifest["estimated_api_requests"] == 4  # 2 movies × 2 requests


# ---------------------------------------------------------------------------
# Full catalog estimation
# ---------------------------------------------------------------------------


class TestFullCatalogEstimation:
    """Tests for estimate_full_catalog_enrichment."""

    def test_estimate_returns_valid_structure(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            estimate_full_catalog_enrichment,
        )

        mapping = MagicMock()
        mapping.total_movielens_movies = 9742
        mapping.movies_with_tmdb_id = 9734
        mapping.movies_without_tmdb_id = 8
        mapping.tmdb_coverage_pct = 99.92

        estimate = estimate_full_catalog_enrichment(mapping)

        assert estimate["report_type"] == "phase8d_full_catalog_estimate"
        assert estimate["catalog"]["total_movies"] == 9742
        assert estimate["request_estimate"]["base_requests"] == 9734 * 2
        assert estimate["request_estimate"]["requests_per_movie"] == 2
        assert estimate["duration_estimate"]["rate_limit_rps"] == 4.0
        assert estimate["storage_estimate"]["total_mb"] > 0
        assert estimate["approval_required"] is True

    def test_estimate_with_custom_rate_limit(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            estimate_full_catalog_enrichment,
        )

        mapping = MagicMock()
        mapping.total_movielens_movies = 100
        mapping.movies_with_tmdb_id = 100
        mapping.movies_without_tmdb_id = 0
        mapping.tmdb_coverage_pct = 100.0

        estimate = estimate_full_catalog_enrichment(mapping, rate_limit_rps=2.0)

        assert estimate["duration_estimate"]["rate_limit_rps"] == 2.0
        # 200 base + 10 retries = 210 total, at 2 RPS = 105 seconds
        assert estimate["duration_estimate"]["estimated_seconds"] > 0

    def test_estimate_zero_movies(self):
        """Works with zero movies."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            estimate_full_catalog_enrichment,
        )

        mapping = MagicMock()
        mapping.total_movielens_movies = 0
        mapping.movies_with_tmdb_id = 0
        mapping.movies_without_tmdb_id = 0
        mapping.tmdb_coverage_pct = 0.0

        estimate = estimate_full_catalog_enrichment(mapping)
        assert estimate["request_estimate"]["base_requests"] == 0
        assert estimate["storage_estimate"]["total_mb"] == 0


# ---------------------------------------------------------------------------
# LivePilotSummary
# ---------------------------------------------------------------------------


class TestLivePilotSummary:
    """Tests for LivePilotSummary.to_dict."""

    def test_to_dict(self):
        from app.recommendation_evaluation.phase8d_live_pilot import LivePilotSummary

        summary = LivePilotSummary(
            pilot_size=40,
            total_attempted=40,
            successful=35,
            identity_conflicts=3,
            not_found=2,
            request_budget=120,
            total_requests=80,
        )
        d = summary.to_dict()
        assert d["pilot_size"] == 40
        assert d["success_rate_pct"] == 87.5
        assert d["request_budget_remaining"] == 40

    def test_to_dict_zero_attempted(self):
        from app.recommendation_evaluation.phase8d_live_pilot import LivePilotSummary

        summary = LivePilotSummary()
        d = summary.to_dict()
        assert d["success_rate_pct"] == 0.0

    def test_to_dict_all_fields_present(self):
        """to_dict contains all expected keys."""
        from app.recommendation_evaluation.phase8d_live_pilot import LivePilotSummary

        summary = LivePilotSummary(pilot_size=10, total_attempted=10, successful=10)
        d = summary.to_dict()
        expected_keys = {
            "pilot_size",
            "seed",
            "is_live",
            "verification_mode",
            "total_attempted",
            "successful",
            "identity_verified",
            "identity_conflicts",
            "not_found",
            "api_errors",
            "skipped",
            "total_requests",
            "request_budget",
            "request_budget_remaining",
            "http_429_count",
            "retry_count",
            "latency_p50_ms",
            "latency_p95_ms",
            "success_rate_pct",
            "field_completeness",
        }
        assert expected_keys.issubset(d.keys())

    def test_success_rate_calculation(self):
        from app.recommendation_evaluation.phase8d_live_pilot import LivePilotSummary

        summary = LivePilotSummary(
            pilot_size=10, total_attempted=4, successful=3
        )
        d = summary.to_dict()
        assert d["success_rate_pct"] == 75.0


# ---------------------------------------------------------------------------
# Quality report
# ---------------------------------------------------------------------------


class TestQualityReport:
    """Tests for generate_pilot_quality_report."""

    def test_generate_creates_json_and_csv(self, tmp_path):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            LivePilotSummary,
            LiveRetrievalRecord,
            generate_pilot_quality_report,
        )

        summary = LivePilotSummary(pilot_size=1, total_attempted=1)
        summary.records.append(
            LiveRetrievalRecord(
                movielens_id="1",
                tmdb_id=862,
                imdb_id="tt0114709",
                movielens_title="Toy Story (1995)",
                movielens_year=1995,
                tmdb_title="",
                tmdb_original_title="",
                tmdb_release_date="",
                status="not_run",
                verification_status="NOT_RUN",
                title_match=False,
                year_match=False,
                fields_retrieved=[],
                fields_missing=["all"],
                request_count=0,
                latency_ms=0.0,
            )
        )

        result = generate_pilot_quality_report(summary, tmp_path)
        assert result.exists()
        assert (tmp_path / "phase8d_data_quality.json").exists()
        assert (tmp_path / "phase8d_per_movie_quality.csv").exists()

        report = json.loads(
            (tmp_path / "phase8d_data_quality.json").read_text()
        )
        assert report["report_type"] == "phase8d_data_quality"
        assert len(report["per_movie_records"]) == 1

    def test_quality_report_record_fields(self, tmp_path):
        """Quality report per-movie records have expected fields."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            LivePilotSummary,
            LiveRetrievalRecord,
            generate_pilot_quality_report,
        )

        summary = LivePilotSummary(pilot_size=1, total_attempted=1, successful=1)
        summary.records.append(
            LiveRetrievalRecord(
                movielens_id="1",
                tmdb_id=862,
                imdb_id="tt0114709",
                movielens_title="Toy Story (1995)",
                movielens_year=1995,
                tmdb_title="Toy Story",
                tmdb_original_title="Toy Story",
                tmdb_release_date="1995-10-30",
                status="success",
                verification_status="LIVE_VERIFIED",
                title_match=True,
                year_match=True,
                fields_retrieved=["overview", "genres"],
                fields_missing=[],
                request_count=2,
                latency_ms=150.0,
                has_overview=True,
                has_keywords=True,
            )
        )

        generate_pilot_quality_report(summary, tmp_path)
        report = json.loads(
            (tmp_path / "phase8d_data_quality.json").read_text()
        )
        record = report["per_movie_records"][0]
        assert record["movielens_id"] == "1"
        assert record["status"] == "success"
        assert record["verification_status"] == "LIVE_VERIFIED"
        assert record["has_overview"] is True
        assert record["has_keywords"] is True

    def test_quality_report_csv_rows(self, tmp_path):
        """CSV quality report has header + 1 row per record."""
        import csv as csv_mod

        from app.recommendation_evaluation.phase8d_live_pilot import (
            LivePilotSummary,
            LiveRetrievalRecord,
            generate_pilot_quality_report,
        )

        summary = LivePilotSummary(pilot_size=2, total_attempted=2)
        for mid in ["1", "2"]:
            summary.records.append(
                LiveRetrievalRecord(
                    movielens_id=mid,
                    tmdb_id=862,
                    imdb_id="tt0114709",
                    movielens_title=f"Movie {mid}",
                    movielens_year=1995,
                    tmdb_title="",
                    tmdb_original_title="",
                    tmdb_release_date="",
                    status="not_run",
                    verification_status="NOT_RUN",
                    title_match=False,
                    year_match=False,
                    fields_retrieved=[],
                    fields_missing=["all"],
                    request_count=0,
                    latency_ms=0.0,
                )
            )

        generate_pilot_quality_report(summary, tmp_path)
        csv_path = tmp_path / "phase8d_per_movie_quality.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv_mod.reader(f)
            rows = list(reader)
        assert len(rows) == 3  # header + 2 data rows


# ---------------------------------------------------------------------------
# LiveRetrievalRecord
# ---------------------------------------------------------------------------


class TestLiveRetrievalRecord:
    """Tests for LiveRetrievalRecord dataclass."""

    def test_default_fields(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            LiveRetrievalRecord,
        )

        record = LiveRetrievalRecord(
            movielens_id="1",
            tmdb_id=862,
            imdb_id="tt0114709",
            movielens_title="Toy Story (1995)",
            movielens_year=1995,
            tmdb_title="Toy Story",
            tmdb_original_title="Toy Story",
            tmdb_release_date="1995-10-30",
            status="success",
            verification_status="LIVE_VERIFIED",
            title_match=True,
            year_match=True,
            fields_retrieved=["overview"],
            fields_missing=[],
            request_count=2,
            latency_ms=150.0,
        )
        # Check defaults
        assert record.error_message == ""
        assert record.has_overview is False
        assert record.has_keywords is False
        assert record.has_cast is False
        assert record.has_director is False
        assert record.has_vi_title is False
        assert record.has_vi_overview is False


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_default_pilot_size(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            PHASE8D_DEFAULT_PILOT_SIZE,
        )

        assert PHASE8D_DEFAULT_PILOT_SIZE == 40

    def test_default_seed(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            PHASE8D_DEFAULT_SEED,
        )

        assert PHASE8D_DEFAULT_SEED == 8042

    def test_default_request_budget(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            PHASE8D_APPROVED_MAX_REQUESTS,
            PHASE8D_DEFAULT_REQUEST_BUDGET,
        )

        assert PHASE8D_DEFAULT_REQUEST_BUDGET == 74
        assert PHASE8D_APPROVED_MAX_REQUESTS == 74

    def test_authorization_env_name(self):
        from app.recommendation_evaluation.phase8d_live_pilot import (
            PHASE8D_AUTHORIZATION_ENV,
        )

        assert PHASE8D_AUTHORIZATION_ENV == "PHASE8D_LIVE_AUTHORIZED"


# ---------------------------------------------------------------------------
# Normalize title helper
# ---------------------------------------------------------------------------


class TestNormalizeTitle:
    """Tests for _normalize_title helper."""

    def test_strips_year_suffix(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _normalize_title

        assert _normalize_title("Toy Story (1995)") == "toy story"

    def test_no_year_suffix(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _normalize_title

        assert _normalize_title("Toy Story") == "toy story"

    def test_lowercase(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _normalize_title

        assert _normalize_title("THE MATRIX (1999)") == "the matrix"

    def test_whitespace_handling(self):
        from app.recommendation_evaluation.phase8d_live_pilot import _normalize_title

        assert _normalize_title("  Toy Story  (1995)  ") == "toy story"


# ---------------------------------------------------------------------------
# Strict Request Budget Enforcement (74 HTTP attempts including retries)
# ---------------------------------------------------------------------------


class TestStrictBudgetEnforcement:
    """Verify TMDBClient and run_live_pilot strictly enforce the 74-attempt hard cap."""

    def test_tmdb_client_stops_before_exceeding_max_total_requests_with_retries(self):
        """Retries, HTTP 429s, 5xxs, timeouts, and vi-VN calls all count toward max_total_requests."""
        import httpx
        from app.core.api_errors import TMDB_BUDGET_EXHAUSTED
        from app.services.tmdb_client import TMDBClient, TMDBClientError, TMDBConfig

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count in (1, 2):
                # First two attempts return 503 Service Unavailable (triggers retry)
                return httpx.Response(503, json={"status_message": "Service Unavailable"})
            if call_count == 3:
                # Third attempt returns 429 Too Many Requests
                return httpx.Response(429, headers={"Retry-After": "0.01"}, json={"status_message": "Rate limit"})
            return httpx.Response(
                200,
                json={
                    "id": 862,
                    "title": "Toy Story",
                    "original_title": "Toy Story",
                    "release_date": "1995-10-30",
                    "overview": "Toys come to life.",
                },
            )

        transport = httpx.MockTransport(handler)
        config = TMDBConfig(
            read_access_token="valid_test_token_123456",
            enable_live_requests=True,
            max_retries=5,
            backoff_base_seconds=0.001,
            rate_limit_rps=100.0,
            max_total_requests=3,  # Hard cap of 3 attempts total!
        )
        client = TMDBClient(config=config, transport=transport, sleep_fn=lambda _: None)

        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(862, language="en-US")

        # Exactly 3 HTTP attempts were sent; the 4th retry was blocked before sending!
        assert call_count == 3
        assert client.stats.requests_total == 3
        assert client.stats.http_5xx_count == 2
        assert client.stats.http_429_count == 1
        assert client.stats.retry_count == 2
        assert exc_info.value.code in (TMDB_BUDGET_EXHAUSTED, "tmdb_rate_limited")

        # Any subsequent call immediately raises TMDB_BUDGET_EXHAUSTED without sending a 4th HTTP request
        with pytest.raises(TMDBClientError) as exc_info2:
            client.get_movie_details(862, language="vi-VN")
        assert exc_info2.value.code == TMDB_BUDGET_EXHAUSTED
        assert call_count == 3
        assert client.stats.requests_total == 3

    def test_live_pilot_preserves_all_manifest_records_on_budget_exhaustion(self, tmp_path):
        """When budget is exhausted mid-run, all manifest records remain in summary with accurate statuses."""
        import httpx
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            run_live_pilot,
        )
        from app.services.tmdb_client import TMDBClient, TMDBConfig

        dataset = MagicMock()
        dataset.movies = {}
        for mid, title in [
            ("1", "Toy Story (1995)"),
            ("2", "Jumanji (1995)"),
            ("3", "Heat (1995)"),
            ("2851", "Missing TMDB Movie (1999)"),
        ]:
            m = MagicMock()
            m.title = title
            m.genres = ["Drama"]
            m.tags = []
            dataset.movies[mid] = m

        mapping = MagicMock()
        mapping.tmdb_lookup = {"1": 862, "2": 8844, "3": 949, "2851": None}
        mapping.imdb_lookup = {"1": "0114709", "2": "0113497", "3": "0113277", "2851": "0123456"}
        mapping.title_year_index = {
            "1": ("Toy Story", 1995),
            "2": ("Jumanji", 1995),
            "3": ("Heat", 1995),
            "2851": ("Missing TMDB Movie", 1999),
        }

        http_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal http_calls
            http_calls += 1
            url = str(request.url)
            if "/movie/862" in url:
                title = "Toy Story"
            elif "/movie/8844" in url:
                title = "Jumanji"
            else:
                title = "Heat"
            return httpx.Response(
                200,
                json={
                    "id": 862,
                    "title": title,
                    "original_title": title,
                    "release_date": "1995-10-30",
                    "overview": "Test overview",
                    "genres": [{"id": 1, "name": "Drama"}],
                    "credits": {"cast": [{"id": 1, "name": "Actor"}], "crew": [{"id": 2, "name": "Dir", "job": "Director"}]},
                    "keywords": {"keywords": [{"id": 10, "name": "test"}]},
                },
            )

        transport = httpx.MockTransport(handler)

        config = Phase8DPilotConfig(
            pilot_size=4,
            request_budget=3,  # Enough for Movie 1 (2 reqs) + Movie 2 EN (1 req), then exhausted on Movie 2 VI!
            dry_run=False,
            live_authorized=True,
            output_dir=tmp_path,
            checkpoint_dir=tmp_path / "checkpoint",
        )

        with (
            patch.dict(
                os.environ,
                {
                    "PHASE8D_LIVE_AUTHORIZED": "true",
                    "TMDB_ENABLE_LIVE_REQUESTS": "true",
                    "TMDB_API_READ_ACCESS_TOKEN": "valid_test_token_123456",
                },
                clear=False,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                side_effect=lambda m, mid: m.tmdb_lookup.get(mid),
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                side_effect=lambda m, mid: m.imdb_lookup.get(mid),
            ),
        ):
            summary = run_live_pilot(
                ["1", "2", "3", "2851"],
                dataset,
                mapping,
                config,
                tmp_path,
                transport=transport,
                sleep_fn=lambda _: None,
            )

        # Hard cap of 3 HTTP attempts must be respected!
        assert http_calls == 3
        assert summary.total_requests == 3
        assert len(summary.records) == 4

        by_id = {r.movielens_id: r for r in summary.records}
        # Movie 1: 2 requests (EN + VI) -> LIVE_VERIFIED
        assert by_id["1"].verification_status == "LIVE_VERIFIED"
        assert by_id["1"].request_count == 2
        # Movie 2: 1 request (EN succeeded, VI hit budget cap) -> PARTIALLY_VERIFIED
        assert by_id["2"].verification_status == "PARTIALLY_VERIFIED"
        assert by_id["2"].request_count == 1
        # Movie 3: 0 requests (budget already 3/3) -> NOT_ATTEMPTED
        assert by_id["3"].verification_status == "NOT_ATTEMPTED"
        assert by_id["3"].request_count == 0
        # Movie 2851: missing TMDB ID -> NOT_ATTEMPTED_MISSING_TMDB_ID
        assert by_id["2851"].verification_status == "NOT_ATTEMPTED_MISSING_TMDB_ID"
        assert by_id["2851"].request_count == 0

    def test_checkpoint_persists_cumulative_requests_across_resumed_runs(self, tmp_path):
        """Resuming from checkpoint restores cumulative_requests so total HTTP attempts never exceed budget."""
        import httpx
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            run_live_pilot,
        )

        dataset = MagicMock()
        dataset.movies = {}
        for mid, title in [("1", "Toy Story (1995)"), ("2", "Jumanji (1995)"), ("3", "Heat (1995)")]:
            m = MagicMock()
            m.title = title
            m.genres = ["Drama"]
            m.tags = []
            dataset.movies[mid] = m

        mapping = MagicMock()
        mapping.tmdb_lookup = {"1": 862, "2": 8844, "3": 949}
        mapping.imdb_lookup = {"1": "0114709", "2": "0113497", "3": "0113277"}
        mapping.title_year_index = {
            "1": ("Toy Story", 1995),
            "2": ("Jumanji", 1995),
            "3": ("Heat", 1995),
        }

        total_network_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal total_network_calls
            total_network_calls += 1
            return httpx.Response(
                200,
                json={
                    "id": 862,
                    "title": "Toy Story",
                    "original_title": "Toy Story",
                    "release_date": "1995-10-30",
                    "overview": "Test overview",
                },
            )

        transport = httpx.MockTransport(handler)

        config = Phase8DPilotConfig(
            pilot_size=3,
            request_budget=4,  # 4 total requests across ALL runs
            dry_run=False,
            live_authorized=True,
            output_dir=tmp_path,
            checkpoint_dir=tmp_path / "checkpoint",
        )

        with (
            patch.dict(
                os.environ,
                {
                    "PHASE8D_LIVE_AUTHORIZED": "true",
                    "TMDB_ENABLE_LIVE_REQUESTS": "true",
                    "TMDB_API_READ_ACCESS_TOKEN": "valid_test_token_123456",
                },
                clear=False,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                side_effect=lambda m, mid: m.tmdb_lookup.get(mid),
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                side_effect=lambda m, mid: m.imdb_lookup.get(mid),
            ),
        ):
            # Run 1: processes movies 1 and 2 (4 requests), movie 3 is not_attempted_budget_exhausted
            summary1 = run_live_pilot(
                ["1", "2", "3"],
                dataset,
                mapping,
                config,
                tmp_path,
                transport=transport,
                sleep_fn=lambda _: None,
            )
            assert total_network_calls == 4
            assert summary1.total_requests == 4

            # Run 2 (resumed with same checkpoint dir): must see cumulative_requests=4 and make 0 additional calls!
            summary2 = run_live_pilot(
                ["1", "2", "3"],
                dataset,
                mapping,
                config,
                tmp_path,
                transport=transport,
                sleep_fn=lambda _: None,
            )
            assert total_network_calls == 4
            assert summary2.total_requests == 4

    def test_missing_credentials_records_blocker_with_zero_requests(self, tmp_path):
        """When TMDB_API_READ_ACCESS_TOKEN is missing, live mode stops cleanly with 0 requests and preserves all movies."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DPilotConfig,
            run_live_pilot,
        )

        dataset = MagicMock()
        dataset.movies = {}
        for mid, title in [("1", "Toy Story (1995)"), ("2851", "Missing TMDB (1999)")]:
            m = MagicMock()
            m.title = title
            m.genres = ["Drama"]
            m.tags = []
            dataset.movies[mid] = m

        mapping = MagicMock()
        mapping.tmdb_lookup = {"1": 862, "2851": None}
        mapping.imdb_lookup = {"1": "0114709", "2851": "0123456"}
        mapping.title_year_index = {"1": ("Toy Story", 1995), "2851": ("Missing TMDB", 1999)}

        config = Phase8DPilotConfig(
            pilot_size=2,
            request_budget=74,
            dry_run=False,
            live_authorized=True,
            output_dir=tmp_path,
            checkpoint_dir=tmp_path / "checkpoint",
        )

        with (
            patch.dict(
                os.environ,
                {
                    "PHASE8D_LIVE_AUTHORIZED": "true",
                    "TMDB_ENABLE_LIVE_REQUESTS": "true",
                },
                clear=False,
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_tmdb_id_for_movie",
                side_effect=lambda m, mid: m.tmdb_lookup.get(mid),
            ),
            patch(
                "app.recommendation_evaluation.phase8d_live_pilot.get_imdb_id_for_movie",
                side_effect=lambda m, mid: m.imdb_lookup.get(mid),
            ),
        ):
            os.environ.pop("TMDB_API_READ_ACCESS_TOKEN", None)
            summary = run_live_pilot(["1", "2851"], dataset, mapping, config, tmp_path)

        assert summary.total_requests == 0
        assert summary.blocker_code == "tmdb_not_configured"
        assert summary.verification_mode == "NOT_RUN"
        assert len(summary.records) == 2
        assert all(r.request_count == 0 for r in summary.records)

    def test_concurrent_pilot_lock_prevents_bypass(self, tmp_path):
        """A second concurrent runner cannot acquire pilot.lock."""
        from app.recommendation_evaluation.phase8d_live_pilot import (
            Phase8DAuthorizationError,
            _acquire_pilot_lock,
            _release_pilot_lock,
        )

        lock_path = _acquire_pilot_lock(tmp_path)
        try:
            with pytest.raises(Phase8DAuthorizationError, match="Concurrent Phase 8D pilot execution detected"):
                _acquire_pilot_lock(tmp_path)
        finally:
            _release_pilot_lock(lock_path)

        # After release, lock can be acquired again
        lock_path2 = _acquire_pilot_lock(tmp_path)
        _release_pilot_lock(lock_path2)

