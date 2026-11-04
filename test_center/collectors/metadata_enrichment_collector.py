"""Metadata enrichment collector for MovSug Test & Evaluation Center (Phase 8A).

Collects or executes the controlled Phase 8A metadata enrichment benchmark and
extracts all 17 required TEC metrics:
  1. total_movies_inspected
  2. movies_with_missing_metadata
  3. completeness_before (field-level breakdown + overall ratio)
  4. completeness_after (field-level breakdown + overall ratio)
  5. candidates_found
  6. verified_id_matches
  7. ambiguous_matches
  8. no_match_cases
  9. admin_approval_rate
  10. rejection_rate
  11. api_failures
  12. http_429_responses
  13. retry_counts
  14. processing_time_p50_ms & processing_time_p95_ms
  15. duplicate_or_conflicting_records
  16. db_application_failures
  17. successful_cache_refreshes
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from ..config.settings import TECSettings
    from .base import CollectorResult
except ImportError:
    from config.settings import TECSettings
    from collectors.base import CollectorResult

logger = logging.getLogger(__name__)

REQUIRED_ENRICHMENT_KEYS: tuple[str, ...] = (
    "total_movies_inspected",
    "movies_with_missing_metadata",
    "completeness_before",
    "completeness_after",
    "candidates_found",
    "verified_id_matches",
    "ambiguous_matches",
    "no_match_cases",
    "admin_approval_rate",
    "rejection_rate",
    "api_failures",
    "http_429_responses",
    "retry_counts",
    "processing_time_p50_ms",
    "processing_time_p95_ms",
    "duplicate_or_conflicting_records",
    "db_application_failures",
    "successful_cache_refreshes",
    "evidence_type",
)


class MetadataEnrichmentCollector:
    """Collects Phase 8A movie metadata enrichment metrics for TEC."""

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    @property
    def summary_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8a_enrichment"
            / "enrichment_evaluation_summary.json"
        )

    def collect_existing(self) -> dict[str, Any] | None:
        """Read and validate an existing Phase 8A enrichment summary artifact."""
        path = self.summary_path
        if not path.is_file():
            logger.info("Phase 8A enrichment summary not found at %s", path)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

        missing = [k for k in REQUIRED_ENRICHMENT_KEYS if k not in data]
        if missing:
            logger.warning("Enrichment summary missing required keys: %s", missing)
            return None

        # Never allow mocked verification to be mislabeled as live-verified
        if data.get("evidence_type") not in ("mocked_controlled_verification", "live_verified"):
            data["evidence_type"] = "mocked_controlled_verification"

        return data

    def collect_or_run(self) -> CollectorResult:
        """
        Return a `CollectorResult` containing the Phase 8A metadata enrichment
        metrics, executing the controlled benchmark if no artifact exists yet.
        """
        start = time.monotonic()
        existing = self.collect_existing()
        if existing is not None:
            duration = time.monotonic() - start
            return CollectorResult(
                suite_name="metadata-enrichment",
                status="PASS",
                duration_seconds=duration,
                tests_total=int(existing.get("total_movies_inspected", 0)),
                tests_passed=int(existing.get("approved_jobs_count", 0))
                + int(existing.get("rejected_jobs_count", 0))
                + int(existing.get("no_match_cases", 0)),
                tests_failed=int(existing.get("db_application_failures", 0)),
                metadata=existing,
            )

        return self.run_benchmark()

    def run_benchmark(self) -> CollectorResult:
        """Execute `python -m app.services.metadata_enrichment_benchmark` via backend venv."""
        python = self._settings.venv_python
        if not python.is_file():
            return CollectorResult.not_run(
                "metadata-enrichment",
                reason=f"venv python not found: {python}",
            )

        cmd = [str(python), "-m", "app.services.metadata_enrichment_benchmark"]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._settings.backend_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            duration = time.monotonic() - start
        except Exception as exc:
            duration = time.monotonic() - start
            return CollectorResult(
                suite_name="metadata-enrichment",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        if proc.returncode != 0:
            return CollectorResult(
                suite_name="metadata-enrichment",
                status="FAIL",
                duration_seconds=duration,
                metadata={
                    "returncode": proc.returncode,
                    "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
                },
            )

        data = self.collect_existing() or {}
        return CollectorResult(
            suite_name="metadata-enrichment",
            status="PASS" if data else "FAIL",
            duration_seconds=duration,
            tests_total=int(data.get("total_movies_inspected", 0)),
            tests_passed=int(data.get("approved_jobs_count", 0))
            + int(data.get("rejected_jobs_count", 0))
            + int(data.get("no_match_cases", 0)),
            tests_failed=int(data.get("db_application_failures", 0)),
            metadata=data,
        )
