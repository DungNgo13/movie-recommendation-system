"""Phase 8C TEC collector tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure test_center is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from test_center.collectors.phase8c_collector import Phase8CCollector, REQUIRED_PHASE8C_KEYS
from test_center.config.settings import TECSettings


@pytest.fixture
def mock_settings(tmp_path: Path) -> TECSettings:
    """Create a TECSettings pointing to a temp directory."""
    # Create the expected backend directory structure
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "frontend").mkdir(parents=True, exist_ok=True)
    return TECSettings.from_root(tmp_path)


@pytest.fixture
def sample_phase8c_summary() -> dict:
    """Minimal valid Phase 8C evaluation summary."""
    return {
        "phase": "Phase 8C",
        "timestamp_utc": "2026-11-06T00:00:00Z",
        "dataset_checksum": "abc123",
        "split_checksum": "xyz789",
        "links_checksum": "links_hash",
        "snapshot_id": "phase8c_test",
        "cohort": {"catalog_size": 9742},
        "identity_mapping": {"total_movielens_movies": 9742, "movies_with_tmdb_id": 9734},
        "enrichment": {"pilot_sample_size": 200, "seed": 8042},
        "evaluation_cells": {
            "A_tfidf_original": {"cell": "A", "model": "TF-IDF v1.1"},
            "B_tfidf_enriched": {"cell": "B", "model": "TF-IDF v1.1"},
            "C_semantic_en_original": {"cell": "C", "model": "Semantic-EN"},
            "D_semantic_en_enriched": {"cell": "D", "model": "Semantic-EN"},
            "E_semantic_multi_original": {"cell": "E", "model": "Semantic-Multi"},
            "F_semantic_multi_enriched": {"cell": "F", "model": "Semantic-Multi"},
        },
        "statistical_comparisons": {},
        "coverage_sensitivity": {"evidence_status": "INSUFFICIENT EVIDENCE"},
        "temporal_validity": {"constraint": "temporal mismatch"},
    }


class TestPhase8CCollector:
    """Tests for Phase8CCollector."""

    def test_collect_existing_missing_file(self, mock_settings):
        """Returns None when summary file does not exist."""
        collector = Phase8CCollector(mock_settings)
        assert collector.collect_existing() is None

    def test_collect_existing_valid_file(self, mock_settings, sample_phase8c_summary):
        """Reads and validates a valid summary file."""
        collector = Phase8CCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8c_research"
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "phase8c_evaluation_summary.json"
        summary_path.write_text(json.dumps(sample_phase8c_summary), encoding="utf-8")

        result = collector.collect_existing()
        assert result is not None
        assert result["phase"] == "Phase 8C"

    def test_collect_existing_missing_keys(self, mock_settings):
        """Returns None when summary is missing required keys."""
        collector = Phase8CCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8c_research"
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "phase8c_evaluation_summary.json"
        summary_path.write_text(json.dumps({"phase": "Phase 8C"}), encoding="utf-8")

        result = collector.collect_existing()
        assert result is None

    def test_collect_or_run_not_found(self, mock_settings):
        """Returns NOT_RUN when no artifacts exist."""
        collector = Phase8CCollector(mock_settings)
        result = collector.collect_or_run()
        assert result.status == "NOT_RUN"
        assert result.suite_name == "phase8c-research"

    def test_collect_or_run_existing(self, mock_settings, sample_phase8c_summary):
        """Returns PASS with correct test counts when artifacts exist."""
        collector = Phase8CCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8c_research"
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "phase8c_evaluation_summary.json"
        summary_path.write_text(json.dumps(sample_phase8c_summary), encoding="utf-8")

        result = collector.collect_or_run()
        assert result.status == "PASS"
        assert result.tests_total == 6  # 6 evaluation cells
        assert result.tests_passed == 6

    def test_required_keys_constant(self):
        """All expected keys are in REQUIRED_PHASE8C_KEYS."""
        assert "phase" in REQUIRED_PHASE8C_KEYS
        assert "evaluation_cells" in REQUIRED_PHASE8C_KEYS
        assert "identity_mapping" in REQUIRED_PHASE8C_KEYS
        assert "temporal_validity" in REQUIRED_PHASE8C_KEYS
