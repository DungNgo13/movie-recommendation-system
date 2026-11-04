"""Tests for Phase 8A MetadataEnrichmentCollector and TEC reporting."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from test_center.collectors.metadata_enrichment_collector import (
    MetadataEnrichmentCollector,
    REQUIRED_ENRICHMENT_KEYS,
)
from test_center.config.settings import TECSettings
from test_center.reporting.html_report import generate_html_report
from test_center.reporting.markdown_report import generate_markdown_report


def _sample_enrichment_summary() -> dict:
    return {
        "phase": "Phase 8A — Movie Metadata Enrichment Foundation",
        "evidence_type": "mocked_controlled_verification",
        "total_movies_inspected": 16,
        "movies_with_missing_metadata": 16,
        "completeness_before": {
            "overall_completeness_ratio": 0.2656,
            "fields": {
                "cast": {"populated": 0, "missing": 16, "completeness_ratio": 0.0},
                "keywords": {"populated": 0, "missing": 16, "completeness_ratio": 0.0},
            },
        },
        "completeness_after": {
            "overall_completeness_ratio": 0.849,
            "fields": {
                "cast": {"populated": 13, "missing": 3, "completeness_ratio": 0.8125},
                "keywords": {"populated": 13, "missing": 3, "completeness_ratio": 0.8125},
            },
        },
        "candidates_found": 20,
        "verified_id_matches": 2,
        "ambiguous_matches": 3,
        "no_match_cases": 1,
        "admin_approval_rate": 0.8667,
        "rejection_rate": 0.1333,
        "approved_jobs_count": 13,
        "rejected_jobs_count": 2,
        "reviewed_jobs_count": 15,
        "api_failures": 0,
        "http_429_responses": 1,
        "retry_counts": 1,
        "processing_time_p50_ms": 2.46,
        "processing_time_p95_ms": 3.61,
        "duplicate_or_conflicting_records": 15,
        "db_application_failures": 0,
        "successful_cache_refreshes": 13,
    }


def test_collector_reads_and_validates_all_17_metrics(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend"
    frontend_dir = tmp_path / "frontend"
    backend_dir.mkdir()
    frontend_dir.mkdir()

    settings = TECSettings.from_root(tmp_path)
    collector = MetadataEnrichmentCollector(settings)

    # Initially missing -> None
    assert collector.collect_existing() is None

    # Write valid summary artifact
    summary = _sample_enrichment_summary()
    collector.summary_path.parent.mkdir(parents=True, exist_ok=True)
    collector.summary_path.write_text(json.dumps(summary), encoding="utf-8")

    collected = collector.collect_existing()
    assert collected is not None
    for key in REQUIRED_ENRICHMENT_KEYS:
        assert key in collected

    result = collector.collect_or_run()
    assert result.status == "PASS"
    assert result.tests_total == 16
    assert result.metadata["evidence_type"] == "mocked_controlled_verification"


def test_markdown_and_html_reports_render_metadata_enrichment(tmp_path: Path) -> None:
    report_data = {
        "metadata": {
            "run_id": "20261104-080000-test",
            "timestamp_utc": "2026-11-04T08:00:00Z",
            "git_commit": "abc1234",
            "platform_info": "Windows",
        },
        "overall_status": "PASS",
        "summary": {
            "functional": {"total": 10, "passed": 10, "failed": 0, "skipped": 0, "status": "PASS"},
            "backend_tests": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "status": "PASS"},
            "frontend_tests": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "status": "PASS"},
            "recommendations": {"status": "PASS", "algorithm": "TF-IDF v1.1 + MMR", "record_count": 3},
        },
        "functional_tests": [],
        "recommendation_metrics": {},
        "metadata_enrichment": _sample_enrichment_summary(),
        "known_limitations": [],
    }

    md_path = generate_markdown_report(report_data, tmp_path / "report.md")
    md_text = md_path.read_text(encoding="utf-8")
    assert "Phase 8A — Movie Metadata Enrichment" in md_text
    assert "mocked_controlled_verification" in md_text
    assert "26.56%" in md_text
    assert "84.90%" in md_text

    html_path = generate_html_report(report_data, tmp_path / "report.html")
    html_text = html_path.read_text(encoding="utf-8")
    assert "Phase 8A — Movie Metadata Enrichment" in html_text
    assert "mocked_controlled_verification" in html_text
