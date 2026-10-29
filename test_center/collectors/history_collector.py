"""Historical phase data collector.

Imports experiment records and audit documents from Phase 1–6 into
structured history records for regression tracking.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config.settings import TECSettings
from ..parsers.experiment_json import (
    parse_ablation_summary,
    parse_experiment_metrics,
    parse_mmr_ablation_summary,
)
from .base import CollectorResult

logger = logging.getLogger(__name__)

# Map experiment directories to phase labels
_PHASE_MAP: dict[str, str] = {
    "baseline_tfidf_v1_0": "Phase 4 — TF-IDF v1.0 Baseline",
    "tfidf_v1_1_controlled_ablation": "Phase 5 — TF-IDF v1.1 Ablation",
    "phase5_5_verification": "Phase 5.5 — Reproducibility Verification",
    "mmr_controlled_ablation": "Phase 6 — MMR Controlled Ablation",
}

# Map audit doc filename patterns to phases
_AUDIT_PHASE_MAP: list[tuple[str, str]] = [
    ("OFFLINE_RECOMMENDATION_EVALUATION", "Phase 4"),
    ("PHASE4_PHASE5_DISCREPANCY", "Phase 5.5"),
    ("REPRODUCED_ABLATION", "Phase 5.5"),
    ("MMR_EXPERIMENT_PROTOCOL", "Phase 6"),
    ("MMR_ABLATION_RESULTS", "Phase 6"),
    ("MMR_STATISTICAL_ANALYSIS", "Phase 6"),
    ("MMR_RELEVANCE_DIVERSITY", "Phase 6"),
    ("VERIFIED_EXPERIMENT_PROTOCOL", "Phase 5.5"),
    ("VERIFIED_STATISTICAL_ANALYSIS", "Phase 5.5"),
]


def _detect_phase_from_filename(name: str) -> str:
    """Detect the phase from an audit document filename."""
    upper = name.upper()
    for pattern, phase in _AUDIT_PHASE_MAP:
        if pattern in upper:
            return phase
    return "Unknown"


class HistoryCollector:
    """Collect historical phase data from experiment reports and audit docs.

    Args:
        settings: TEC settings providing paths to experiment reports
            and audit documentation.
    """

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    def collect(self) -> CollectorResult:
        """Scan experiment reports and audit docs to build history.

        Returns:
            A :class:`CollectorResult` with historical records stored
            in ``metadata["historical_records"]``.
        """
        records: list[dict[str, Any]] = []
        errors: list[str] = []

        # 1) Collect from experiment JSON files
        exp_records = self._collect_experiment_history(errors)
        records.extend(exp_records)

        # 2) Collect from audit documentation
        audit_records = self._collect_audit_history(errors)
        records.extend(audit_records)

        # Sort by timestamp (or phase order)
        records.sort(key=lambda r: (r.get("phase", ""), r.get("timestamp_utc", "")))

        status = "PASS" if not errors else "MIXED"
        return CollectorResult(
            suite_name="history-import",
            status=status,
            tests_total=len(records),
            tests_passed=len(records),
            metadata={
                "historical_records": records,
                "experiment_count": len(exp_records),
                "audit_doc_count": len(audit_records),
                "errors": errors,
            },
        )

    def _collect_experiment_history(
        self, errors: list[str]
    ) -> list[dict[str, Any]]:
        """Parse experiment JSON files into history records."""
        exp_dir = self._settings.experiment_reports_dir
        records: list[dict[str, Any]] = []

        if not exp_dir.is_dir():
            logger.warning("Experiment reports dir not found: %s", exp_dir)
            return records

        for sub in sorted(exp_dir.iterdir()):
            if not sub.is_dir():
                continue

            phase_label = _PHASE_MAP.get(sub.name, f"Unknown ({sub.name})")

            # Single metrics.json
            metrics_file = sub / "metrics.json"
            if metrics_file.is_file():
                try:
                    rec = parse_experiment_metrics(metrics_file)
                    records.append({
                        "phase": phase_label,
                        "experiment_id": rec.experiment_id,
                        "algorithm_name": rec.algorithm_name,
                        "algorithm_version": rec.algorithm_version,
                        "timestamp_utc": rec.timestamp_utc,
                        "git_commit": rec.git_commit,
                        "dataset_checksum": rec.dataset_checksum,
                        "split_checksum": rec.split_checksum,
                        "evidence_type": "IMPORTED",
                        "validation_status": "VERIFIED",
                        "source_path": str(metrics_file),
                    })
                except Exception as exc:
                    errors.append(f"Failed to parse {metrics_file}: {exc}")

            # Ablation summary
            ablation_file = sub / "ablation_summary.json"
            if ablation_file.is_file():
                try:
                    variants = parse_ablation_summary(ablation_file)
                    for vkey, vrec in variants.items():
                        records.append({
                            "phase": phase_label,
                            "experiment_id": vrec.experiment_id,
                            "algorithm_name": vrec.algorithm_name,
                            "algorithm_version": vrec.algorithm_version,
                            "timestamp_utc": vrec.timestamp_utc,
                            "git_commit": vrec.git_commit,
                            "dataset_checksum": vrec.dataset_checksum,
                            "split_checksum": vrec.split_checksum,
                            "evidence_type": "IMPORTED",
                            "validation_status": "VERIFIED",
                            "source_path": str(ablation_file),
                        })
                except Exception as exc:
                    errors.append(f"Failed to parse {ablation_file}: {exc}")

            # MMR ablation
            mmr_file = sub / "mmr_ablation_summary.json"
            if mmr_file.is_file():
                try:
                    variants = parse_mmr_ablation_summary(mmr_file)
                    for vkey, vrec in variants.items():
                        records.append({
                            "phase": phase_label,
                            "experiment_id": vrec.experiment_id,
                            "algorithm_name": vrec.algorithm_name,
                            "algorithm_version": vrec.algorithm_version,
                            "timestamp_utc": vrec.timestamp_utc,
                            "git_commit": vrec.git_commit,
                            "dataset_checksum": vrec.dataset_checksum,
                            "split_checksum": vrec.split_checksum,
                            "evidence_type": "IMPORTED",
                            "validation_status": "VERIFIED",
                            "source_path": str(mmr_file),
                        })
                except Exception as exc:
                    errors.append(f"Failed to parse {mmr_file}: {exc}")

        logger.info("Collected %d experiment history records", len(records))
        return records

    def _collect_audit_history(
        self, errors: list[str]
    ) -> list[dict[str, Any]]:
        """Scan audit documentation for narrative-only records."""
        audit_dir = self._settings.audit_docs_dir
        records: list[dict[str, Any]] = []

        if not audit_dir.is_dir():
            logger.warning("Audit docs dir not found: %s", audit_dir)
            return records

        for doc in sorted(audit_dir.iterdir()):
            if not doc.is_file() or doc.suffix.lower() != ".md":
                continue

            phase = _detect_phase_from_filename(doc.stem)

            # Try to extract timestamp from file content
            timestamp = ""
            try:
                content = doc.read_text(encoding="utf-8")[:2000]
                # Look for ISO date patterns
                match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", content)
                if match:
                    timestamp = match.group(0)
            except Exception:
                pass

            records.append({
                "phase": phase,
                "experiment_id": doc.stem,
                "algorithm_name": "Narrative documentation",
                "algorithm_version": "",
                "timestamp_utc": timestamp,
                "git_commit": "",
                "dataset_checksum": "",
                "split_checksum": "",
                "evidence_type": "NARRATIVE_ONLY",
                "validation_status": "UNVERIFIED",
                "source_path": str(doc),
            })

        logger.info("Collected %d audit doc records", len(records))
        return records
