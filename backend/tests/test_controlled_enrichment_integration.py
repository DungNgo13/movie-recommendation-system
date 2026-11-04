"""
Automated pytest verification of the 16-movie controlled enrichment benchmark (Phase 8A).

Ensures that:
  - All 16 representative movies (exact ID, IMDb ID, bilingual titles, common title,
    remake disambiguation, sequel disambiguation, missing overview/cast/keywords,
    HTTP 429 retry recovery, conflicting year rejection, ambiguous adaptation rejection,
    and no-match case) execute end-to-end in an isolated database.
  - All 17 TEC metadata enrichment metrics are recorded accurately.
  - Evidence is labeled `mocked_controlled_verification` (never falsely claiming live verification).
"""

from __future__ import annotations

from app.services.metadata_enrichment_benchmark import (
    TRACKED_COMPLETENESS_FIELDS,
    run_controlled_enrichment_benchmark,
)


def test_controlled_16_movie_enrichment_integration(tmp_path):
    out_file = tmp_path / "enrichment_evaluation_summary.json"
    summary = run_controlled_enrichment_benchmark(output_json_path=out_file)

    assert out_file.is_file()
    assert summary["evidence_type"] == "mocked_controlled_verification"
    assert summary["total_movies_inspected"] == 16
    assert summary["movies_with_missing_metadata"] == 16

    before = summary["completeness_before"]
    after = summary["completeness_after"]
    assert after["overall_completeness_ratio"] > before["overall_completeness_ratio"]
    assert after["overall_completeness_ratio"] >= 0.80

    for field in TRACKED_COMPLETENESS_FIELDS:
        assert field in before["fields"]
        assert field in after["fields"]
        assert after["fields"][field]["populated"] >= before["fields"][field]["populated"]

    # Matching & review telemetry assertions
    assert summary["candidates_found"] >= 16
    assert summary["verified_id_matches"] == 2
    assert summary["ambiguous_matches"] >= 2
    assert summary["no_match_cases"] == 1
    assert summary["approved_jobs_count"] == 13
    assert summary["rejected_jobs_count"] == 2
    assert summary["reviewed_jobs_count"] == 15
    assert 0.80 <= summary["admin_approval_rate"] <= 0.90
    assert 0.10 <= summary["rejection_rate"] <= 0.20

    # API & operational telemetry assertions
    assert summary["api_failures"] == 0
    assert summary["http_429_responses"] == 1
    assert summary["retry_counts"] == 1
    assert summary["processing_time_p50_ms"] >= 0.0
    assert summary["processing_time_p95_ms"] >= summary["processing_time_p50_ms"]
    assert summary["duplicate_or_conflicting_records"] >= 3
    assert summary["db_application_failures"] == 0
    assert summary["successful_cache_refreshes"] == 13
    assert summary["cache_generation_after"] > summary["cache_generation_before"]
    assert len(summary["per_movie_results"]) == 16

