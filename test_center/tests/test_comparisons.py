"""Tests for TEC regression analysis."""
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
        """Verify pass rate delta is computed correctly."""
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
        """Both runs with no tests should be STABLE."""
        empty = {
            "functional_tests": [],
            "recommendation_metrics": {},
        }
        analyzer = RegressionAnalyzer(empty, empty)
        result = analyzer.compare()
        assert result["overall_verdict"] == "STABLE"
