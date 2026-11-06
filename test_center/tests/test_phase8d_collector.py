"""Phase 8D TEC collector tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure test_center is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from test_center.collectors.phase8d_collector import Phase8DCollector, REQUIRED_PHASE8D_MANIFEST_KEYS
from test_center.config.settings import TECSettings


@pytest.fixture
def mock_settings(tmp_path: Path) -> TECSettings:
    """Create a TECSettings pointing to a temp directory."""
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "frontend").mkdir(parents=True, exist_ok=True)
    return TECSettings.from_root(tmp_path)


@pytest.fixture
def sample_phase8d_manifest() -> dict:
    """Minimal valid Phase 8D pilot manifest."""
    return {
        "manifest_type": "phase8d_pilot_manifest",
        "generated_at": "2026-11-06T00:00:00Z",
        "pilot_size": 40,
        "seed": 8042,
        "estimated_api_requests": 74,
        "movies": [{"movielens_id": "1", "title": "Toy Story (1995)"}],
    }


@pytest.fixture
def sample_phase8d_quality() -> dict:
    """Minimal valid Phase 8D quality report."""
    return {
        "report_type": "phase8d_data_quality",
        "generated_at": "2026-11-06T00:00:00Z",
        "summary": {
            "pilot_size": 40,
            "verification_mode": "NOT_RUN",
            "total_attempted": 40,
            "successful": 0,
        },
        "per_movie_records": [],
    }


class TestPhase8DCollector:
    """Tests for Phase8DCollector."""

    def test_collect_existing_missing_file(self, mock_settings):
        """Returns None when manifest file does not exist."""
        collector = Phase8DCollector(mock_settings)
        assert collector.collect_existing() is None

    def test_collect_existing_valid_file(self, mock_settings, sample_phase8d_manifest):
        """Reads and validates a valid manifest file."""
        collector = Phase8DCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8d_pilot"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "phase8d_pilot_manifest.json").write_text(
            json.dumps(sample_phase8d_manifest), encoding="utf-8"
        )
        result = collector.collect_existing()
        assert result is not None
        assert result["manifest_type"] == "phase8d_pilot_manifest"

    def test_collect_existing_missing_keys(self, mock_settings):
        """Returns None when manifest is missing required keys."""
        collector = Phase8DCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8d_pilot"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "phase8d_pilot_manifest.json").write_text(
            json.dumps({"manifest_type": "phase8d_pilot_manifest"}), encoding="utf-8"
        )
        result = collector.collect_existing()
        assert result is None

    def test_collect_or_run_not_found(self, mock_settings):
        """Returns NOT_RUN when no artifacts exist."""
        collector = Phase8DCollector(mock_settings)
        result = collector.collect_or_run()
        assert result.status == "NOT_RUN"
        assert result.suite_name == "phase8d-pilot"

    def test_collect_or_run_with_manifest(self, mock_settings, sample_phase8d_manifest):
        """Returns PASS with correct test counts when manifest exists."""
        collector = Phase8DCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8d_pilot"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "phase8d_pilot_manifest.json").write_text(
            json.dumps(sample_phase8d_manifest), encoding="utf-8"
        )
        result = collector.collect_or_run()
        assert result.status == "PASS"
        assert result.tests_total == 1  # number of movies in manifest

    def test_collect_or_run_with_both_artifacts(
        self, mock_settings, sample_phase8d_manifest, sample_phase8d_quality
    ):
        """Returns PASS with quality report in metadata when both exist."""
        collector = Phase8DCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8d_pilot"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "phase8d_pilot_manifest.json").write_text(
            json.dumps(sample_phase8d_manifest), encoding="utf-8"
        )
        (report_dir / "phase8d_data_quality.json").write_text(
            json.dumps(sample_phase8d_quality), encoding="utf-8"
        )
        result = collector.collect_or_run()
        assert result.status == "PASS"
        assert result.metadata["quality_report"] is not None

    def test_required_keys_constant(self):
        """All expected keys are in REQUIRED_PHASE8D_MANIFEST_KEYS."""
        assert "manifest_type" in REQUIRED_PHASE8D_MANIFEST_KEYS
        assert "pilot_size" in REQUIRED_PHASE8D_MANIFEST_KEYS
        assert "movies" in REQUIRED_PHASE8D_MANIFEST_KEYS

    def test_collect_quality_report_missing(self, mock_settings):
        """Returns None when quality report does not exist."""
        collector = Phase8DCollector(mock_settings)
        assert collector.collect_quality_report() is None

    def test_collect_quality_report_valid(self, mock_settings, sample_phase8d_quality):
        """Reads valid quality report."""
        collector = Phase8DCollector(mock_settings)
        report_dir = mock_settings.backend_dir / "reports" / "phase8d_pilot"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "phase8d_data_quality.json").write_text(
            json.dumps(sample_phase8d_quality), encoding="utf-8"
        )
        result = collector.collect_quality_report()
        assert result is not None
        assert result["report_type"] == "phase8d_data_quality"

    def test_manifest_path_property(self, mock_settings):
        """manifest_path points to the expected location."""
        collector = Phase8DCollector(mock_settings)
        expected = (
            mock_settings.backend_dir / "reports" / "phase8d_pilot" / "phase8d_pilot_manifest.json"
        )
        assert collector.manifest_path == expected

    def test_quality_path_property(self, mock_settings):
        """quality_report_path points to the expected location."""
        collector = Phase8DCollector(mock_settings)
        expected = (
            mock_settings.backend_dir / "reports" / "phase8d_pilot" / "phase8d_data_quality.json"
        )
        assert collector.quality_report_path == expected
