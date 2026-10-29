"""Tests for TEC parsers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.junit_xml import parse_junit_xml
from parsers.experiment_json import (
    ExperimentRecord,
    parse_experiment_metrics,
    parse_ablation_summary,
)


class TestJunitXmlParser:
    """Tests for parse_junit_xml."""

    def test_basic_counts(self, sample_junit_xml: Path) -> None:
        """Verify total, failures, skipped, and passed counts."""
        result = parse_junit_xml(sample_junit_xml)
        assert result.tests == 5
        assert result.failures == 1
        assert result.skipped == 1
        assert result.passed == 3

    def test_test_case_details(self, sample_junit_xml: Path) -> None:
        """Verify individual test case names and statuses."""
        result = parse_junit_xml(sample_junit_xml)
        cases = {tc.name: tc for tc in result.test_cases}

        assert "test_login_success" in cases
        assert cases["test_login_success"].status == "passed"

        assert "test_delete_movie" in cases
        assert cases["test_delete_movie"].status == "failed"
        assert "403" in (cases["test_delete_movie"].message or "")

        assert "test_upload_disabled" in cases
        assert cases["test_upload_disabled"].status == "skipped"

    def test_missing_file(self, tmp_path: Path) -> None:
        """Verify FileNotFoundError for missing XML."""
        with pytest.raises(FileNotFoundError):
            parse_junit_xml(tmp_path / "nonexistent.xml")

    def test_empty_suite(self, tmp_path: Path) -> None:
        """Verify handling of an XML with zero test cases."""
        xml = '<?xml version="1.0"?><testsuite name="empty" tests="0"/>'
        path = tmp_path / "empty.xml"
        path.write_text(xml, encoding="utf-8")

        result = parse_junit_xml(path)
        assert result.tests == 0
        assert result.passed == 0
        assert result.test_cases == []

    def test_suite_name(self, sample_junit_xml: Path) -> None:
        """Verify suite name is extracted."""
        result = parse_junit_xml(sample_junit_xml)
        assert result.name == "pytest"

    def test_pass_rate(self, sample_junit_xml: Path) -> None:
        """Verify pass rate calculation."""
        result = parse_junit_xml(sample_junit_xml)
        assert result.pass_rate == pytest.approx(3 / 5)


class TestExperimentMetricsParser:
    """Tests for parse_experiment_metrics."""

    def test_basic_fields(self, sample_metrics_json: Path) -> None:
        """Verify experiment record fields are parsed correctly."""
        rec = parse_experiment_metrics(sample_metrics_json)
        assert rec.experiment_id == "test_baseline"
        assert rec.algorithm_name == "TF-IDF v1.0"
        assert rec.algorithm_version == "1.0.0"
        assert rec.git_commit == "abc1234def5678"

    def test_checksums(self, sample_metrics_json: Path) -> None:
        """Verify checksums are parsed from the nested structure."""
        rec = parse_experiment_metrics(sample_metrics_json)
        assert rec.dataset_checksum.startswith("696d65a3")
        assert rec.split_checksum.startswith("48cc8f10")
        assert rec.config_checksum == "deadbeef1234567890abcdef"

    def test_metrics_by_k(self, sample_metrics_json: Path) -> None:
        """Verify metrics_by_k contains expected values."""
        rec = parse_experiment_metrics(sample_metrics_json)
        assert "k_5" in rec.metrics_by_k
        assert "k_10" in rec.metrics_by_k
        assert rec.metrics_by_k["k_5"]["precision"] == pytest.approx(0.05)
        assert rec.metrics_by_k["k_10"]["ndcg"] == pytest.approx(0.10)

    def test_evidence_type(self, sample_metrics_json: Path) -> None:
        """Verify imported records are labeled IMPORTED."""
        rec = parse_experiment_metrics(sample_metrics_json)
        assert rec.evidence_type == "IMPORTED"

    def test_to_dict(self, sample_metrics_json: Path) -> None:
        """Verify to_dict serialization."""
        rec = parse_experiment_metrics(sample_metrics_json)
        d = rec.to_dict()
        assert isinstance(d, dict)
        assert d["experiment_id"] == "test_baseline"
        assert d["evidence_type"] == "IMPORTED"

    def test_missing_file(self, tmp_path: Path) -> None:
        """Verify FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_experiment_metrics(tmp_path / "nonexistent.json")


class TestAblationSummaryParser:
    """Tests for parse_ablation_summary."""

    def test_variant_count(self, sample_ablation_json: Path) -> None:
        """Verify two variants are parsed."""
        variants = parse_ablation_summary(sample_ablation_json)
        assert len(variants) == 2
        assert "v1.0_baseline" in variants
        assert "v1.1_r1r2r3" in variants

    def test_variant_fields(self, sample_ablation_json: Path) -> None:
        """Verify variant record fields."""
        variants = parse_ablation_summary(sample_ablation_json)
        v10 = variants["v1.0_baseline"]
        assert v10.algorithm_name == "TF-IDF v1.0 (Baseline)"
        assert v10.config_checksum == "aaa111"
        assert v10.evidence_type == "IMPORTED"

    def test_variant_metrics(self, sample_ablation_json: Path) -> None:
        """Verify variant metrics are parsed."""
        variants = parse_ablation_summary(sample_ablation_json)
        v11 = variants["v1.1_r1r2r3"]
        assert v11.metrics_by_k["k_10"]["ndcg"] == pytest.approx(0.12)

    def test_missing_file(self, tmp_path: Path) -> None:
        """Verify FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_ablation_summary(tmp_path / "nonexistent.json")
