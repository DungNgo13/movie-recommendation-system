"""Semantic recommendation experiment collector for MovSug TEC (Phase 8B).

Collects and validates the Phase 8B Semantic Embeddings & Metadata Quality
Ablation evaluation artifacts from
``backend/reports/phase8b_embeddings/phase8b_evaluation_summary.json``:
  1. Model names, revisions, embedding dimensions, and configuration checksums
  2. Metadata condition (`A_Original`, `B1_Full_Partial_Enriched`, `B2_Matched_Subset`)
  3. Dataset, split, metadata snapshot, and vector cache SHA-256 checksums
  4. Top-K ranking, diversity, coverage, and novelty metrics (K=5, 10, 20)
  5. Paired statistical significance tests, 95% bootstrap CIs, Cohen's d, and
     Win/Tie/Loss counts across RQ1, RQ2, and RQ3
  6. Operational costs (embedding generation duration, cache load time, storage
     footprint, peak memory MB, p50/p95 recommendation latency, cold-start
     latency, missing-vector rate, and fallback rate)
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

REQUIRED_PHASE8B_KEYS: tuple[str, ...] = (
    "phase",
    "timestamp_utc",
    "git_commit",
    "dataset_checksum",
    "split_checksum",
    "cohort",
    "condition_a_variants",
    "ablation_2x2",
    "statistical_comparisons",
    "performance_benchmark",
)


class SemanticRecommendationCollector:
    """Collects Phase 8B semantic embedding & metadata ablation metrics for TEC."""

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    @property
    def summary_path(self) -> Path:
        return (
            self._settings.backend_dir
            / "reports"
            / "phase8b_embeddings"
            / "phase8b_evaluation_summary.json"
        )

    def collect_existing(self) -> dict[str, Any] | None:
        """Read and validate an existing Phase 8B evaluation summary JSON."""
        path = self.summary_path
        if not path.is_file():
            logger.info("Phase 8B evaluation summary not found at %s", path)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to parse %s", path)
            return None

        missing = [k for k in REQUIRED_PHASE8B_KEYS if k not in data]
        if missing:
            logger.warning("Phase 8B summary missing required keys: %s", missing)
            return None

        return data

    def collect_or_run(self) -> CollectorResult:
        """
        Return a ``CollectorResult`` containing the Phase 8B semantic embedding
        evaluation metrics, or ``NOT_RUN`` if the artifact is not yet present.
        """
        start = time.monotonic()
        existing = self.collect_existing()
        if existing is not None:
            duration = time.monotonic() - start
            variants = existing.get("condition_a_variants", {})
            return CollectorResult(
                suite_name="semantic-recommendation",
                status="PASS",
                duration_seconds=duration,
                tests_total=len(variants),
                tests_passed=len(variants),
                tests_failed=0,
                metadata=existing,
            )

        return CollectorResult.not_run(
            "semantic-recommendation",
            reason=f"Phase 8B summary not found at {self.summary_path}",
        )

    def run_evaluation(self, allow_download: bool = False) -> CollectorResult:
        """Execute ``python -m app.recommendation_evaluation.run --phase8b``."""
        python = self._settings.venv_python
        if not python.is_file():
            return CollectorResult.not_run(
                "semantic-recommendation",
                reason=f"venv python not found: {python}",
            )

        cmd = [
            str(python),
            "-m",
            "app.recommendation_evaluation.run",
            "--phase8b",
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
                timeout=900,
            )
            duration = time.monotonic() - start
        except Exception as exc:
            duration = time.monotonic() - start
            return CollectorResult(
                suite_name="semantic-recommendation",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        if proc.returncode != 0:
            return CollectorResult(
                suite_name="semantic-recommendation",
                status="FAIL",
                duration_seconds=duration,
                metadata={
                    "returncode": proc.returncode,
                    "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
                },
            )

        data = self.collect_existing() or {}
        variants = data.get("condition_a_variants", {})
        return CollectorResult(
            suite_name="semantic-recommendation",
            status="PASS" if data else "FAIL",
            duration_seconds=duration,
            tests_total=len(variants),
            tests_passed=len(variants),
            tests_failed=0,
            metadata=data,
        )
