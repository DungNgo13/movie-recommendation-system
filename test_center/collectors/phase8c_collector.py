"""Phase 8C research metadata enrichment collector for MovSug TEC.

Collects and validates the Phase 8C MovieLens-TMDB Identity Mapping,
Research Metadata Enrichment, and Controlled Re-evaluation artifacts from
``backend/reports/phase8c_research/phase8c_evaluation_summary.json``:
  1. Identity mapping coverage (MovieLens → TMDB mapping audit)
  2. Metadata retrieval success rate and field-level completeness
  3. Research metadata snapshot provenance and checksums
  4. 6-cell evaluation matrix (A–F) metrics at K=5, 10, 20
  5. Statistical comparisons with paired significance tests
  6. Coverage sensitivity and temporal validity analysis
  7. Data quality and failure reports
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

REQUIRED_PHASE8C_KEYS: tuple[str, ...] = (
    "phase",
    "timestamp_utc",
    "dataset_checksum",
    "split_checksum",
    "links_checksum",
    "snapshot_id",
    "cohort",
    "identity_mapping",
    "enrichment",
    "evaluation_cells",
    "statistical_comparisons",
    "coverage_sensitivity",
    "temporal_validity",
)


class Phase8CCollector:
    """Collects Phase 8C identity mapping, enrichment, and evaluation metrics for TEC."""

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    @property
    def summary_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8c_research"
            / "phase8c_evaluation_summary.json"
        )

    @property
    def identity_report_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8c_research"
            / "phase8c_identity_coverage.json"
        )

    @property
    def coverage_report_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8c_research"
            / "phase8c_field_coverage.json"
        )

    def collect_existing(self) -> dict[str, Any] | None:
        """Read and validate an existing Phase 8C evaluation summary JSON."""
        path = self.summary_path
        if not path.is_file():
            logger.info("Phase 8C evaluation summary not found at %s", path)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

        missing = [k for k in REQUIRED_PHASE8C_KEYS if k not in data]
        if missing:
            logger.warning("Phase 8C summary missing required keys: %s", missing)
            return None

        return data

    def collect_identity_report(self) -> dict[str, Any] | None:
        """Read the Phase 8C identity coverage report."""
        path = self.identity_report_path
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

    def collect_coverage_report(self) -> dict[str, Any] | None:
        """Read the Phase 8C field-level coverage report."""
        path = self.coverage_report_path
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

    def collect_or_run(self) -> CollectorResult:
        """
        Return a ``CollectorResult`` containing Phase 8C evaluation metrics,
        or ``NOT_RUN`` if the artifact is not yet present.
        """
        start = time.monotonic()
        existing = self.collect_existing()
        if existing is not None:
            duration = time.monotonic() - start
            cells = existing.get("evaluation_cells", {})
            identity_report = self.collect_identity_report()
            coverage_report = self.collect_coverage_report()

            metadata = {
                "evaluation_summary": existing,
                "identity_report": identity_report,
                "coverage_report": coverage_report,
            }

            return CollectorResult(
                suite_name="phase8c-research",
                status="PASS",
                duration_seconds=duration,
                tests_total=len(cells),
                tests_passed=len(cells),
                tests_failed=0,
                metadata=metadata,
            )

        return CollectorResult.not_run(
            "phase8c-research",
            reason=f"Phase 8C summary not found at {self.summary_path}",
        )

    def run_evaluation(
        self,
        allow_download: bool = False,
        pilot_size: int = 200,
    ) -> CollectorResult:
        """Execute ``python -m app.recommendation_evaluation.cli --phase8c``."""
        python = self._settings.venv_python
        if not python.is_file():
            return CollectorResult.not_run(
                "phase8c-research",
                reason=f"venv python not found: {python}",
            )

        cmd = [
            str(python),
            "-m",
            "app.recommendation_evaluation.cli",
            "--phase8c",
            "--phase8c-pilot-size",
            str(pilot_size),
        ]
        if allow_download:
            cmd.append("--allow-model-download")

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._settings.backend_dir),
                capture_output=True,
                text=True,
                timeout=1800,
            )
            duration = time.monotonic() - start
        except Exception as exc:
            duration = time.monotonic() - start
            return CollectorResult(
                suite_name="phase8c-research",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        if proc.returncode != 0:
            return CollectorResult(
                suite_name="phase8c-research",
                status="FAIL",
                duration_seconds=duration,
                metadata={
                    "returncode": proc.returncode,
                    "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
                },
            )

        data = self.collect_existing() or {}
        cells = data.get("evaluation_cells", {})
        return CollectorResult(
            suite_name="phase8c-research",
            status="PASS" if data else "FAIL",
            duration_seconds=duration,
            tests_total=len(cells),
            tests_passed=len(cells),
            tests_failed=0,
            metadata=data,
        )
