"""Parser for experiment JSON files produced by the recommendation evaluation.

Handles three JSON layouts found under ``backend/reports/experiments/``:

* **metrics.json** — single-experiment result with top-level
  ``experiment_id``, ``checksums``, and ``metrics`` keys.
* **ablation_summary.json** — controlled ablation with ``variants`` mapping
  variant labels to per-variant metrics.
* **mmr_ablation_summary.json** — MMR ablation with the same ``variants``
  structure but different variant naming.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExperimentRecord:
    """Normalised representation of a single experiment variant.

    Attributes:
        experiment_id: Unique experiment identifier.
        algorithm_name: Human-readable algorithm name.
        algorithm_version: Semantic version of the algorithm.
        git_commit: Git SHA at experiment time.
        timestamp_utc: ISO-8601 timestamp.
        dataset_checksum: SHA-256 of the raw dataset.
        split_checksum: SHA-256 of the train/test split.
        config_checksum: SHA-256 of the experiment configuration.
        metrics_by_k: Mapping of ``k_N`` → metric dict.
        latency: Latency percentiles (``p50_ms``, ``p90_ms``, etc.).
        cohort: Evaluation cohort metadata.
        source_path: File path the record was parsed from.
        evidence_type: ``EXECUTED`` (freshly run) or ``IMPORTED``
            (parsed from existing reports).
    """

    experiment_id: str
    algorithm_name: str
    algorithm_version: str
    git_commit: str
    timestamp_utc: str
    dataset_checksum: str
    split_checksum: str
    config_checksum: str
    metrics_by_k: dict[str, dict[str, float]] = field(default_factory=dict)
    latency: dict[str, float] = field(default_factory=dict)
    cohort: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""
    evidence_type: str = "IMPORTED"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "experiment_id": self.experiment_id,
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "git_commit": self.git_commit,
            "timestamp_utc": self.timestamp_utc,
            "dataset_checksum": self.dataset_checksum,
            "split_checksum": self.split_checksum,
            "config_checksum": self.config_checksum,
            "metrics_by_k": self.metrics_by_k,
            "latency": self.latency,
            "cohort": self.cohort,
            "source_path": self.source_path,
            "evidence_type": self.evidence_type,
        }


# ---------------------------------------------------------------------------
# Single-experiment metrics.json
# ---------------------------------------------------------------------------

def parse_experiment_metrics(path: Path) -> ExperimentRecord:
    """Parse a single ``metrics.json`` experiment file.

    Expected top-level keys: ``experiment_id``, ``checksums``,
    ``metrics`` (containing ``by_k``, ``latency``,
    ``evaluation_cohort``).

    Args:
        path: Path to the ``metrics.json`` file.

    Returns:
        An :class:`ExperimentRecord` instance.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Experiment metrics not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    checksums = data.get("checksums", {})
    metrics = data.get("metrics", {})
    by_k = metrics.get("by_k", {})
    latency = metrics.get("latency", {})
    cohort = metrics.get("evaluation_cohort", {})

    record = ExperimentRecord(
        experiment_id=data.get("experiment_id", path.parent.name),
        algorithm_name=data.get("algorithm_name", "unknown"),
        algorithm_version=data.get("algorithm_version", "0.0.0"),
        git_commit=data.get("git_commit", "unknown"),
        timestamp_utc=data.get("timestamp_utc", ""),
        dataset_checksum=checksums.get("raw_dataset_sha256", ""),
        split_checksum=checksums.get("split_sha256", ""),
        config_checksum=checksums.get("config_sha256", ""),
        metrics_by_k=by_k,
        latency=latency,
        cohort=cohort,
        source_path=str(path),
        evidence_type="IMPORTED",
    )

    logger.info(
        "Parsed experiment %s (%s) from %s",
        record.experiment_id,
        record.algorithm_name,
        path.name,
    )
    return record


# ---------------------------------------------------------------------------
# Ablation summary (tfidf_v1_1_controlled_ablation)
# ---------------------------------------------------------------------------

def _parse_ablation_variants(
    data: dict[str, Any],
    path: Path,
) -> dict[str, ExperimentRecord]:
    """Shared helper for ablation summary files with a ``variants`` key."""
    top_git = data.get("git_commit", "unknown")
    top_ts = data.get("timestamp_utc", "")
    top_ds = data.get("dataset_checksum", "")
    top_split = data.get("split_checksum", "")
    top_cohort = data.get("cohort", {})

    variants = data.get("variants", {})
    result: dict[str, ExperimentRecord] = {}

    for variant_key, variant_data in variants.items():
        metrics = variant_data.get("metrics", {})
        by_k = metrics.get("by_k", {})
        latency = metrics.get("latency", {})
        cohort = metrics.get("evaluation_cohort", top_cohort)

        record = ExperimentRecord(
            experiment_id=f"{path.parent.name}/{variant_key}",
            algorithm_name=variant_data.get("name", variant_key),
            algorithm_version=variant_data.get("version", ""),
            git_commit=top_git,
            timestamp_utc=top_ts,
            dataset_checksum=top_ds,
            split_checksum=top_split,
            config_checksum=variant_data.get("config_checksum", ""),
            metrics_by_k=by_k,
            latency=latency,
            cohort=cohort,
            source_path=str(path),
            evidence_type="IMPORTED",
        )
        result[variant_key] = record

    logger.info("Parsed %d variants from %s", len(result), path.name)
    return result


def parse_ablation_summary(path: Path) -> dict[str, ExperimentRecord]:
    """Parse an ``ablation_summary.json`` file.

    Args:
        path: Path to the ablation summary JSON.

    Returns:
        Mapping of variant label → :class:`ExperimentRecord`.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Ablation summary not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_ablation_variants(data, path)


def parse_mmr_ablation_summary(path: Path) -> dict[str, ExperimentRecord]:
    """Parse an ``mmr_ablation_summary.json`` file.

    Same layout as :func:`parse_ablation_summary` but may use different
    variant naming conventions (e.g. ``mmr_l0.3_p50``).

    Args:
        path: Path to the MMR ablation summary JSON.

    Returns:
        Mapping of variant label → :class:`ExperimentRecord`.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"MMR ablation summary not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    return _parse_ablation_variants(data, path)
