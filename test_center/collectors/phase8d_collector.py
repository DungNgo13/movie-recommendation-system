"""Phase 8D controlled live TMDB pilot collector for MovSug TEC.

Collects and validates the Phase 8D Controlled Live TMDB Pilot artifacts from
``backend/reports/phase8d_pilot/phase8d_pilot_manifest.json`` and
``backend/reports/phase8d_pilot/phase8d_data_quality.json``:
  1. Pilot manifest (movie selection, seed, estimated API requests)
  2. Data quality report (per-movie verification, summary statistics)
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

REQUIRED_PHASE8D_MANIFEST_KEYS: tuple[str, ...] = (
    "manifest_type",
    "generated_at",
    "pilot_size",
    "seed",
    "estimated_api_requests",
    "movies",
)

REQUIRED_PHASE8D_QUALITY_KEYS: tuple[str, ...] = (
    "report_type",
    "generated_at",
    "summary",
    "per_movie_records",
)


class Phase8DCollector:
    """Collects Phase 8D controlled live TMDB pilot metrics for TEC."""

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    @property
    def manifest_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8d_pilot"
            / "phase8d_pilot_manifest.json"
        )

    @property
    def quality_report_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8d_pilot"
            / "phase8d_data_quality.json"
        )

    def collect_existing(self) -> dict[str, Any] | None:
        """Read and validate an existing Phase 8D pilot manifest JSON."""
        path = self.manifest_path
        if not path.is_file():
            logger.info("Phase 8D pilot manifest not found at %s", path)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

        missing = [k for k in REQUIRED_PHASE8D_MANIFEST_KEYS if k not in data]
        if missing:
            logger.warning("Phase 8D manifest missing required keys: %s", missing)
            return None

        return data

    def collect_quality_report(self) -> dict[str, Any] | None:
        """Read and validate the Phase 8D data quality report."""
        path = self.quality_report_path
        if not path.is_file():
            logger.info("Phase 8D quality report not found at %s", path)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

        missing = [k for k in REQUIRED_PHASE8D_QUALITY_KEYS if k not in data]
        if missing:
            logger.warning("Phase 8D quality report missing required keys: %s", missing)
            return None

        return data

    def collect_or_run(self) -> CollectorResult:
        """
        Return a ``CollectorResult`` containing Phase 8D pilot metrics,
        or ``NOT_RUN`` if the artifact is not yet present.
        """
        start = time.monotonic()
        existing = self.collect_existing()
        if existing is not None:
            duration = time.monotonic() - start
            movies = existing.get("movies", [])
            quality_report = self.collect_quality_report()

            # Extract verification_mode from quality report summary if available
            verification_mode = "NOT_RUN"
            if quality_report and "summary" in quality_report:
                verification_mode = quality_report["summary"].get(
                    "verification_mode", "NOT_RUN"
                )

            metadata = {
                "manifest": existing,
                "quality_report": quality_report,
                "verification_mode": verification_mode,
            }

            return CollectorResult(
                suite_name="phase8d-pilot",
                status="PASS",
                duration_seconds=duration,
                tests_total=len(movies),
                tests_passed=len(movies),
                tests_failed=0,
                metadata=metadata,
            )

        return CollectorResult.not_run(
            "phase8d-pilot",
            reason=f"Phase 8D manifest not found at {self.manifest_path}",
        )

    def run_evaluation(self) -> CollectorResult:
        """Execute ``python -m app.recommendation_evaluation.cli --phase8d``."""
        python = self._settings.venv_python
        if not python.is_file():
            return CollectorResult.not_run(
                "phase8d-pilot",
                reason=f"venv python not found: {python}",
            )

        cmd = [
            str(python),
            "-m",
            "app.recommendation_evaluation.cli",
            "--phase8d",
        ]

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
                suite_name="phase8d-pilot",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        if proc.returncode != 0:
            return CollectorResult(
                suite_name="phase8d-pilot",
                status="FAIL",
                duration_seconds=duration,
                metadata={
                    "returncode": proc.returncode,
                    "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
                },
            )

        data = self.collect_existing() or {}
        movies = data.get("movies", [])
        quality_report = self.collect_quality_report()

        verification_mode = "NOT_RUN"
        if quality_report and "summary" in quality_report:
            verification_mode = quality_report["summary"].get(
                "verification_mode", "NOT_RUN"
            )

        return CollectorResult(
            suite_name="phase8d-pilot",
            status="PASS" if data else "FAIL",
            duration_seconds=duration,
            tests_total=len(movies),
            tests_passed=len(movies),
            tests_failed=0,
            metadata={
                "manifest": data,
                "quality_report": quality_report,
                "verification_mode": verification_mode,
            },
        )
