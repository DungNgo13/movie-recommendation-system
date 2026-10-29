"""Regression analysis for comparing TEC runs.

Compares two run reports (baseline vs candidate) to detect test
regressions, fixes, and metric changes.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Higher is better for these metrics
_HIGHER_IS_BETTER: dict[str, bool] = {
    "precision": True, "recall": True, "ndcg": True,
    "hit_rate": True, "map": True, "catalog_coverage": True,
    "intra_list_diversity": True, "novelty": True,
    "pass_rate": True,
    "p50_ms": False, "p90_ms": False, "p95_ms": False, "mean_ms": False,
}

_PASS_STATES = {"PASS", "PASSED", "SUCCESS"}
_FAIL_STATES = {"FAIL", "FAILED", "ERROR"}


class RegressionAnalyzer:
    """Compare a baseline run with a candidate run.

    Args:
        baseline_data: Full report dict from the baseline run.
        candidate_data: Full report dict from the candidate run.
    """

    def __init__(
        self,
        baseline_data: dict[str, Any],
        candidate_data: dict[str, Any],
    ) -> None:
        self._baseline = baseline_data
        self._candidate = candidate_data

    def compare(self) -> dict[str, Any]:
        """Execute the comparison and return a structured result.

        Returns:
            A dict with keys:
            - ``comparable`` (bool)
            - ``not_comparable_reason`` (str | None)
            - ``functional_diff`` (dict)
            - ``metric_diff`` (dict)
            - ``regressions`` (list)
            - ``fixes`` (list)
            - ``overall_verdict`` (str)
        """
        result: dict[str, Any] = {
            "comparable": True,
            "not_comparable_reason": None,
            "functional_diff": {},
            "metric_diff": {},
            "regressions": [],
            "fixes": [],
            "overall_verdict": "STABLE",
        }

        # Check comparability via checksums
        reason = self._check_comparability()
        if reason:
            result["comparable"] = False
            result["not_comparable_reason"] = reason
            result["overall_verdict"] = "NOT_COMPARABLE"
            logger.warning("Runs are not comparable: %s", reason)
            return result

        # Functional test comparison
        func_diff = self._compare_functional_tests()
        result["functional_diff"] = func_diff
        result["regressions"] = func_diff.get("regressions", [])
        result["fixes"] = func_diff.get("fixes", [])

        # Metric comparison
        metric_diff = self._compare_metrics()
        result["metric_diff"] = metric_diff

        # Determine overall verdict
        result["overall_verdict"] = self._determine_verdict(
            func_diff, metric_diff
        )

        return result

    def _check_comparability(self) -> str | None:
        """Check if the two runs can be meaningfully compared.

        Returns:
            A reason string if they are not comparable, otherwise ``None``.
        """
        b_rec = self._baseline.get("recommendation_metrics", {})
        c_rec = self._candidate.get("recommendation_metrics", {})

        b_ds = b_rec.get("dataset_checksum", "")
        c_ds = c_rec.get("dataset_checksum", "")
        if b_ds and c_ds and b_ds != c_ds:
            return (
                f"Dataset checksums differ: baseline={b_ds[:16]}... "
                f"vs candidate={c_ds[:16]}..."
            )

        b_sp = b_rec.get("split_checksum", "")
        c_sp = c_rec.get("split_checksum", "")
        if b_sp and c_sp and b_sp != c_sp:
            return (
                f"Split checksums differ: baseline={b_sp[:16]}... "
                f"vs candidate={c_sp[:16]}..."
            )

        return None

    def _compare_functional_tests(self) -> dict[str, Any]:
        """Compare functional test results between baseline and candidate."""
        b_tests = self._baseline.get("functional_tests", [])
        c_tests = self._candidate.get("functional_tests", [])

        b_map = {t["name"]: t for t in b_tests if "name" in t}
        c_map = {t["name"]: t for t in c_tests if "name" in t}

        b_names = set(b_map.keys())
        c_names = set(c_map.keys())

        tests_added = sorted(c_names - b_names)
        tests_removed = sorted(b_names - c_names)
        common = b_names & c_names

        tests_changed: list[dict[str, str]] = []
        regressions: list[dict[str, str]] = []
        fixes: list[dict[str, str]] = []

        for name in sorted(common):
            b_status = b_map[name].get("status", "").upper()
            c_status = c_map[name].get("status", "").upper()
            if b_status != c_status:
                change = {
                    "name": name,
                    "baseline_status": b_status,
                    "candidate_status": c_status,
                }
                tests_changed.append(change)

                if b_status in _PASS_STATES and c_status in _FAIL_STATES:
                    regressions.append(change)
                elif b_status in _FAIL_STATES and c_status in _PASS_STATES:
                    fixes.append(change)

        b_total = len(b_tests)
        c_total = len(c_tests)
        b_passed = sum(
            1 for t in b_tests if t.get("status", "").upper() in _PASS_STATES
        )
        c_passed = sum(
            1 for t in c_tests if t.get("status", "").upper() in _PASS_STATES
        )
        b_rate = b_passed / b_total if b_total else 0.0
        c_rate = c_passed / c_total if c_total else 0.0

        return {
            "tests_added": tests_added,
            "tests_removed": tests_removed,
            "tests_changed": tests_changed,
            "regressions": regressions,
            "fixes": fixes,
            "pass_rate_baseline": b_rate,
            "pass_rate_candidate": c_rate,
            "pass_rate_delta": c_rate - b_rate,
        }

    def _compare_metrics(self) -> dict[str, Any]:
        """Compare recommendation metrics between baseline and candidate."""
        b_rec = self._baseline.get("recommendation_metrics", {})
        c_rec = self._candidate.get("recommendation_metrics", {})

        b_by_k = b_rec.get("by_k", {})
        c_by_k = c_rec.get("by_k", {})

        diff: dict[str, Any] = {}

        # Compare by-K metrics
        all_k = sorted(set(b_by_k.keys()) | set(c_by_k.keys()))
        for k_label in all_k:
            b_metrics = b_by_k.get(k_label, {})
            c_metrics = c_by_k.get(k_label, {})
            all_metric_names = sorted(
                set(b_metrics.keys()) | set(c_metrics.keys())
            )
            k_diff: dict[str, Any] = {}
            for m in all_metric_names:
                b_val = b_metrics.get(m)
                c_val = c_metrics.get(m)
                if b_val is not None and c_val is not None:
                    try:
                        b_f = float(b_val)
                        c_f = float(c_val)
                        abs_delta = c_f - b_f
                        rel_delta = (abs_delta / b_f * 100) if b_f != 0 else 0.0
                        higher_better = _HIGHER_IS_BETTER.get(m, True)
                        if abs(abs_delta) < 1e-10:
                            direction = "unchanged"
                        elif (abs_delta > 0) == higher_better:
                            direction = "improved"
                        else:
                            direction = "degraded"
                        k_diff[m] = {
                            "baseline_value": b_f,
                            "candidate_value": c_f,
                            "absolute_delta": abs_delta,
                            "relative_delta_pct": rel_delta,
                            "direction": direction,
                        }
                    except (TypeError, ValueError):
                        pass
            if k_diff:
                diff[k_label] = k_diff

        # Compare latency
        b_lat = b_rec.get("latency", {})
        c_lat = c_rec.get("latency", {})
        if b_lat and c_lat:
            lat_diff: dict[str, Any] = {}
            for m in sorted(set(b_lat.keys()) | set(c_lat.keys())):
                b_val = b_lat.get(m)
                c_val = c_lat.get(m)
                if b_val is not None and c_val is not None:
                    try:
                        b_f = float(b_val)
                        c_f = float(c_val)
                        abs_delta = c_f - b_f
                        rel_delta = (abs_delta / b_f * 100) if b_f != 0 else 0.0
                        higher_better = _HIGHER_IS_BETTER.get(m, False)
                        if abs(abs_delta) < 1e-6:
                            direction = "unchanged"
                        elif (abs_delta > 0) == higher_better:
                            direction = "improved"
                        else:
                            direction = "degraded"
                        lat_diff[m] = {
                            "baseline_value": b_f,
                            "candidate_value": c_f,
                            "absolute_delta": abs_delta,
                            "relative_delta_pct": rel_delta,
                            "direction": direction,
                        }
                    except (TypeError, ValueError):
                        pass
            if lat_diff:
                diff["latency"] = lat_diff

        return diff

    def _determine_verdict(
        self,
        func_diff: dict[str, Any],
        metric_diff: dict[str, Any],
    ) -> str:
        """Determine overall verdict from functional and metric diffs."""
        regressions = func_diff.get("regressions", [])
        fixes = func_diff.get("fixes", [])

        if regressions:
            return "DEGRADED"

        # Check for metric degradation
        degraded_count = 0
        improved_count = 0
        for k_data in metric_diff.values():
            if isinstance(k_data, dict):
                for m_data in k_data.values():
                    if isinstance(m_data, dict):
                        d = m_data.get("direction", "unchanged")
                        if d == "degraded":
                            degraded_count += 1
                        elif d == "improved":
                            improved_count += 1

        if degraded_count > improved_count:
            return "DEGRADED"
        if improved_count > 0 or fixes:
            return "IMPROVED"
        return "STABLE"
