"""Shared fixtures for TEC tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure test-center is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sample_junit_xml(tmp_path: Path) -> Path:
    """Create a sample JUnit XML file with mixed test results."""
    xml_content = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="5" failures="1" errors="0" skipped="1" time="2.345">
  <testcase classname="tests.test_auth" name="test_login_success" time="0.123"/>
  <testcase classname="tests.test_auth" name="test_login_invalid" time="0.045"/>
  <testcase classname="tests.test_movies" name="test_list_movies" time="0.890"/>
  <testcase classname="tests.test_movies" name="test_delete_movie" time="0.567">
    <failure message="AssertionError: 403 != 200">Expected 200 but got 403</failure>
  </testcase>
  <testcase classname="tests.test_r2" name="test_upload_disabled" time="0.020">
    <skipped message="R2 not configured"/>
  </testcase>
</testsuite>
"""
    path = tmp_path / "pytest-results.xml"
    path.write_text(xml_content, encoding="utf-8")
    return path


@pytest.fixture
def sample_metrics_json(tmp_path: Path) -> Path:
    """Create a sample metrics.json experiment file."""
    data = {
        "experiment_id": "test_baseline",
        "algorithm_name": "TF-IDF v1.0",
        "algorithm_version": "1.0.0",
        "git_commit": "abc1234def5678",
        "timestamp_utc": "2026-10-01T00:00:00Z",
        "checksums": {
            "raw_dataset_sha256": "696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436",
            "split_sha256": "48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67",
            "config_sha256": "deadbeef1234567890abcdef",
        },
        "metrics": {
            "by_k": {
                "k_5": {
                    "precision": 0.05,
                    "recall": 0.10,
                    "ndcg": 0.08,
                    "hit_rate": 0.20,
                    "catalog_coverage": 0.0946,
                    "intra_list_diversity": 0.5833,
                },
                "k_10": {
                    "precision": 0.04,
                    "recall": 0.15,
                    "ndcg": 0.10,
                    "hit_rate": 0.25,
                    "catalog_coverage": 0.15,
                    "intra_list_diversity": 0.60,
                },
            },
            "latency": {
                "p50_ms": 1.5,
                "p90_ms": 3.2,
                "p95_ms": 4.1,
                "mean_ms": 2.0,
            },
            "evaluation_cohort": {
                "total_users": 610,
                "eligible_users": 200,
            },
        },
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def sample_ablation_json(tmp_path: Path) -> Path:
    """Create a sample ablation_summary.json with 2 variants."""
    data = {
        "git_commit": "abc1234",
        "timestamp_utc": "2026-10-15T00:00:00Z",
        "dataset_checksum": "696d65a3dfce",
        "split_checksum": "48cc8f10cce9",
        "variants": {
            "v1.0_baseline": {
                "name": "TF-IDF v1.0 (Baseline)",
                "version": "1.0.0",
                "config_checksum": "aaa111",
                "metrics": {
                    "by_k": {
                        "k_5": {"precision": 0.05, "ndcg": 0.08},
                        "k_10": {"precision": 0.04, "ndcg": 0.10},
                    },
                    "latency": {"p50_ms": 1.5, "mean_ms": 2.0},
                },
            },
            "v1.1_r1r2r3": {
                "name": "TF-IDF v1.1 (R1+R2+R3)",
                "version": "1.1.0",
                "config_checksum": "bbb222",
                "metrics": {
                    "by_k": {
                        "k_5": {"precision": 0.06, "ndcg": 0.09},
                        "k_10": {"precision": 0.05, "ndcg": 0.12},
                    },
                    "latency": {"p50_ms": 1.6, "mean_ms": 2.1},
                },
            },
        },
    }
    path = tmp_path / "ablation_summary.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def baseline_report_data() -> dict:
    """Return a dict simulating a baseline TEC run report."""
    return {
        "metadata": {
            "run_id": "tec-20261029-000000-abc1234",
            "timestamp_utc": "2026-10-29T00:00:00Z",
            "git_commit": "abc1234def5678",
        },
        "overall_status": "PASS",
        "summary": {
            "functional": {"total": 4, "passed": 3, "failed": 1, "skipped": 0},
            "backend_tests": {"total": 3, "passed": 2, "failed": 1, "skipped": 0, "status": "FAIL"},
            "frontend_tests": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "status": "PASS"},
        },
        "functional_tests": [
            {"name": "test_login", "classname": "tests.test_auth", "status": "PASSED"},
            {"name": "test_register", "classname": "tests.test_auth", "status": "PASSED"},
            {"name": "test_upload", "classname": "tests.test_r2", "status": "FAILED", "message": "timeout"},
            {"name": "test_list_movies", "classname": "tests.test_movies", "status": "PASSED"},
        ],
        "recommendation_metrics": {
            "by_k": {
                "k_5": {"precision": 0.05, "ndcg": 0.08},
                "k_10": {"precision": 0.04, "ndcg": 0.10},
            },
            "latency": {"p50_ms": 1.5, "mean_ms": 2.0},
            "dataset_checksum": "696d65a3dfce",
            "split_checksum": "48cc8f10cce9",
        },
    }


@pytest.fixture
def candidate_report_data() -> dict:
    """Return a dict simulating a candidate TEC run with one regression."""
    return {
        "metadata": {
            "run_id": "tec-20261029-010000-def5678",
            "timestamp_utc": "2026-10-29T01:00:00Z",
            "git_commit": "def5678abc1234",
        },
        "overall_status": "FAIL",
        "summary": {
            "functional": {"total": 4, "passed": 2, "failed": 2, "skipped": 0},
        },
        "functional_tests": [
            {"name": "test_login", "classname": "tests.test_auth", "status": "FAILED", "message": "500 error"},
            {"name": "test_register", "classname": "tests.test_auth", "status": "PASSED"},
            {"name": "test_upload", "classname": "tests.test_r2", "status": "PASSED"},
            {"name": "test_list_movies", "classname": "tests.test_movies", "status": "PASSED"},
        ],
        "recommendation_metrics": {
            "by_k": {
                "k_5": {"precision": 0.06, "ndcg": 0.09},
                "k_10": {"precision": 0.05, "ndcg": 0.12},
            },
            "latency": {"p50_ms": 1.6, "mean_ms": 2.1},
            "dataset_checksum": "696d65a3dfce",
            "split_checksum": "48cc8f10cce9",
        },
    }
