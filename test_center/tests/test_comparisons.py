"""Tests for TEC regression analysis.

Covers:
- Basic regression / fix detection
- Comparability checks (dataset / split checksums)
- Pass-rate calculation from functional_tests
- Pass-rate fallback from summary counts (legacy Bug #2 fix)
- INCOMPLETE verdict when suites are missing
- Empty-tests edge case
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comparisons.regression import RegressionAnalyzer


class TestRegressionAnalyzer:
    """Tests for RegressionAnalyzer.compare()."""

    def test_identical_is_stable(self, baseline_report_data: dict) -> None:
        """Comparing identical data should yield STABLE verdict."""
        analyzer = RegressionAnalyzer(baseline_report_data, baseline_report_data)
        result = analyzer.compare()
        assert result["comparable"] is True
        assert result["overall_verdict"] == "STABLE"
        assert result["regressions"] == []
        assert result["fixes"] == []

    def test_regression_detected(
        self, baseline_report_data: dict, candidate_report_data: dict
    ) -> None:
        """test_login went PASSED→FAILED: should be a regression."""
        analyzer = RegressionAnalyzer(baseline_report_data, candidate_report_data)
        result = analyzer.compare()
        assert result["comparable"] is True

        regressions = result["regressions"]
        assert len(regressions) == 1
        assert regressions[0]["name"] == "test_login"

    def test_fix_detected(
        self, baseline_report_data: dict, candidate_report_data: dict
    ) -> None:
        """test_upload went FAILED→PASSED: should be a fix."""
        analyzer = RegressionAnalyzer(baseline_report_data, candidate_report_data)
        result = analyzer.compare()

        fixes = result["fixes"]
        assert len(fixes) == 1
        assert fixes[0]["name"] == "test_upload"

    def test_not_comparable_different_dataset(
        self, baseline_report_data: dict
    ) -> None:
        """Different dataset checksums should be NOT_COMPARABLE."""
        candidate = copy.deepcopy(baseline_report_data)
        candidate["recommendation_metrics"]["dataset_checksum"] = "different_checksum"

        analyzer = RegressionAnalyzer(baseline_report_data, candidate)
        result = analyzer.compare()
        assert result["comparable"] is False
        assert result["overall_verdict"] == "NOT_COMPARABLE"
        assert "Dataset checksums differ" in result["not_comparable_reason"]

    def test_not_comparable_different_split(
        self, baseline_report_data: dict
    ) -> None:
        """Different split checksums should be NOT_COMPARABLE."""
        candidate = copy.deepcopy(baseline_report_data)
        candidate["recommendation_metrics"]["split_checksum"] = "different_split"

        analyzer = RegressionAnalyzer(baseline_report_data, candidate)
        result = analyzer.compare()
        assert result["comparable"] is False
        assert result["overall_verdict"] == "NOT_COMPARABLE"

    def test_pass_rate_delta(
        self, baseline_report_data: dict, candidate_report_data: dict
    ) -> None:
        """Verify pass rate delta is computed correctly.

        Baseline: 3/4 passed.  Candidate: 3/4 passed.
        """
        analyzer = RegressionAnalyzer(baseline_report_data, candidate_report_data)
        result = analyzer.compare()
        func = result["functional_diff"]

        assert func["pass_rate_baseline"] == pytest.approx(3 / 4)
        assert func["pass_rate_candidate"] == pytest.approx(3 / 4)
        assert func["pass_rate_delta"] == pytest.approx(0.0)

    def test_metric_improvement(
        self, baseline_report_data: dict, candidate_report_data: dict
    ) -> None:
        """Candidate has better NDCG — should detect improvement."""
        analyzer = RegressionAnalyzer(baseline_report_data, candidate_report_data)
        result = analyzer.compare()
        metric_diff = result["metric_diff"]

        # k_10 ndcg went 0.10 → 0.12
        assert "k_10" in metric_diff
        ndcg_diff = metric_diff["k_10"]["ndcg"]
        assert ndcg_diff["direction"] == "improved"
        assert ndcg_diff["absolute_delta"] == pytest.approx(0.02)

    def test_empty_tests(self) -> None:
        """Both runs with no tests — evidence is 'none', verdict INCOMPLETE."""
        empty = {
            "functional_tests": [],
            "summary": {"functional": {"total": 0, "passed": 0}},
            "recommendation_metrics": {},
        }
        analyzer = RegressionAnalyzer(empty, empty)
        result = analyzer.compare()
        # No evidence available at all; cannot determine stability.
        assert result["overall_verdict"] == "INCOMPLETE"


class TestBug2LegacyFallback:
    """Verify pass-rate uses summary counts when functional_tests is empty."""

    def test_legacy_pass_rate_not_zero(
        self, legacy_report_data_empty_tests: dict
    ) -> None:
        """Bug #2: two legacy runs should NOT produce 0% pass rate."""
        data = legacy_report_data_empty_tests
        analyzer = RegressionAnalyzer(data, data)
        result = analyzer.compare()
        func = result["functional_diff"]

        # Summary says 378/378 passed → 100%
        assert func["pass_rate_baseline"] == pytest.approx(1.0)
        assert func["pass_rate_candidate"] == pytest.approx(1.0)
        assert func["evidence_quality"] == "summary_only"

    def test_legacy_baseline_vs_modern_candidate(
        self,
        legacy_report_data_empty_tests: dict,
        baseline_report_data: dict,
    ) -> None:
        """Legacy baseline (empty tests) compared to modern candidate."""
        analyzer = RegressionAnalyzer(
            legacy_report_data_empty_tests, baseline_report_data
        )
        result = analyzer.compare()
        func = result["functional_diff"]

        # Baseline: 378/378 from summary.  Candidate: 3/4 from functional_tests.
        assert func["pass_rate_baseline"] == pytest.approx(1.0)
        assert func["pass_rate_candidate"] == pytest.approx(3 / 4)
        assert func["evidence_quality"] == "summary_only"


class TestIncompleteVerdict:
    """Test INCOMPLETE verdict when suites are missing."""

    def test_missing_backend_suite(
        self,
        baseline_report_data: dict,
        report_data_missing_suite: dict,
    ) -> None:
        """Candidate has no backend tests but baseline did — INCOMPLETE."""
        analyzer = RegressionAnalyzer(
            baseline_report_data, report_data_missing_suite
        )
        result = analyzer.compare()
        assert result["overall_verdict"] == "INCOMPLETE"
        assert "backend_tests" in result["functional_diff"]["tests_missing"]

    def test_both_have_no_tests_is_stable(self) -> None:
        """Two runs with zero tests total → no evidence → INCOMPLETE."""
        empty = {
            "functional_tests": [],
            "summary": {
                "functional": {"total": 0, "passed": 0},
                "backend_tests": {"total": 0},
                "frontend_tests": {"total": 0},
            },
            "recommendation_metrics": {},
        }
        analyzer = RegressionAnalyzer(empty, empty)
        result = analyzer.compare()
        # No evidence at all
        assert result["functional_diff"]["evidence_quality"] == "none"


class TestEvidenceQuality:
    """Verify evidence_quality field is set correctly."""

    def test_complete_evidence(
        self, baseline_report_data: dict, candidate_report_data: dict
    ) -> None:
        """Both runs have full functional_tests → complete evidence."""
        analyzer = RegressionAnalyzer(baseline_report_data, candidate_report_data)
        result = analyzer.compare()
        assert result["functional_diff"]["evidence_quality"] == "complete"

    def test_summary_only_evidence(
        self, legacy_report_data_empty_tests: dict
    ) -> None:
        """Empty functional_tests with valid summary → summary_only."""
        data = legacy_report_data_empty_tests
        analyzer = RegressionAnalyzer(data, data)
        result = analyzer.compare()
        assert result["functional_diff"]["evidence_quality"] == "summary_only"
