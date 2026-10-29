"""Recommendation experiment collector.

Scans existing experiment reports under
``backend/reports/experiments/`` and optionally re-runs the
evaluation pipeline.
"""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from ..config.settings import TECSettings
from ..parsers.experiment_json import (
    ExperimentRecord,
    parse_ablation_summary,
    parse_experiment_metrics,
    parse_mmr_ablation_summary,
)
from .base import CollectorResult

logger = logging.getLogger(__name__)


class RecommendationCollector:
    """Collect recommendation experiment results.

    Args:
        settings: TEC settings providing experiment report paths.
    """

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    def collect_existing(self) -> list[ExperimentRecord]:
        """Scan existing experiment reports and return parsed records.

        Looks for ``metrics.json``, ``ablation_summary.json``, and
        ``mmr_ablation_summary.json`` files under the configured
        experiment reports directory.

        Returns:
            List of :class:`ExperimentRecord` instances.
        """
        exp_dir = self._settings.experiment_reports_dir
        records: list[ExperimentRecord] = []

        if not exp_dir.is_dir():
            logger.warning("Experiment reports dir not found: %s", exp_dir)
            return records

        for sub in sorted(exp_dir.iterdir()):
            if not sub.is_dir():
                continue

            # Single-experiment metrics.json
            metrics_file = sub / "metrics.json"
            if metrics_file.is_file():
                try:
                    record = parse_experiment_metrics(metrics_file)
                    records.append(record)
                except Exception:
                    logger.exception("Failed to parse %s", metrics_file)

            # Ablation summary
            ablation_file = sub / "ablation_summary.json"
            if ablation_file.is_file():
                try:
                    variants = parse_ablation_summary(ablation_file)
                    records.extend(variants.values())
                except Exception:
                    logger.exception("Failed to parse %s", ablation_file)

            # MMR ablation summary
            mmr_file = sub / "mmr_ablation_summary.json"
            if mmr_file.is_file():
                try:
                    variants = parse_mmr_ablation_summary(mmr_file)
                    records.extend(variants.values())
                except Exception:
                    logger.exception("Failed to parse %s", mmr_file)

        logger.info(
            "Collected %d experiment records from %s",
            len(records),
            exp_dir,
        )
        return records

    def run_evaluation(self, variant: str = "v1.1") -> CollectorResult:
        """Run the recommendation evaluation pipeline.

        Invokes ``python -m app.recommendation_evaluation.run``
        using the backend venv Python.

        Args:
            variant: Algorithm variant to evaluate.

        Returns:
            A :class:`CollectorResult` summarising the evaluation.
        """
        settings = self._settings
        python = settings.venv_python

        if not python.is_file():
            return CollectorResult.not_run(
                "recommendation-eval",
                reason=f"venv python not found: {python}",
            )

        cmd = [
            str(python),
            "-m",
            "app.recommendation_evaluation.run",
            "--variant",
            variant,
        ]

        logger.info("Running: %s", " ".join(cmd))

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(settings.backend_dir),
                capture_output=True,
                text=True,
                timeout=900,  # 15 min max
            )
            duration = time.monotonic() - start
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return CollectorResult(
                suite_name="recommendation-eval",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": "evaluation timed out after 900s"},
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return CollectorResult(
                suite_name="recommendation-eval",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        status = "PASS" if proc.returncode == 0 else "FAIL"
        return CollectorResult(
            suite_name="recommendation-eval",
            status=status,
            duration_seconds=duration,
            metadata={
                "returncode": proc.returncode,
                "variant": variant,
                "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            },
        )
