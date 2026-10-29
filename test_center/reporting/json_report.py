"""JSON report generator for the Test & Evaluation Center.

Produces a structured ``summary.json`` plus subsidiary files for
machine-readable consumption.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_json_report(report_data: dict[str, Any], output_path: Path) -> Path:
    """Write the full report as pretty-printed JSON.

    Also generates subsidiary files in the same directory:

    * ``metrics.csv`` — flattened experiment metrics per variant per K
    * ``test_results.json`` — functional test results only
    * ``failures.json`` — failed tests with messages

    Args:
        report_data: Report dict from a TEC run.
        output_path: Destination for the main ``summary.json`` file.

    Returns:
        The resolved ``output_path`` that was written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Main summary JSON
    output_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("JSON report written to %s", output_path)

    out_dir = output_path.parent

    # test_results.json
    tests = report_data.get("functional_tests", [])
    if tests:
        tr_path = out_dir / "test_results.json"
        tr_path.write_text(
            json.dumps(tests, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info("Test results written to %s", tr_path)

    # failures.json
    failures = [
        t for t in tests
        if t.get("status", "").upper() in ("FAIL", "FAILED", "ERROR")
    ]
    if failures:
        fail_path = out_dir / "failures.json"
        fail_path.write_text(
            json.dumps(failures, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info("Failures written to %s (%d failures)", fail_path, len(failures))

    # metrics.csv
    _write_metrics_csv(report_data, out_dir / "metrics.csv")

    return output_path


def _write_metrics_csv(report_data: dict[str, Any], csv_path: Path) -> None:
    """Flatten experiment metrics into a CSV file."""
    rec = report_data.get("recommendation_metrics", {})
    by_k = rec.get("by_k", {})
    if not by_k:
        return

    # Gather all metric names
    all_metrics: set[str] = set()
    for k_metrics in by_k.values():
        all_metrics.update(k_metrics.keys())

    metric_cols = sorted(all_metrics)
    header = ["k"] + metric_cols

    rows: list[list[str]] = []
    for k_label in sorted(by_k.keys()):
        metrics = by_k[k_label]
        row = [k_label] + [str(metrics.get(m, "")) for m in metric_cols]
        rows.append(row)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    logger.info("Metrics CSV written to %s (%d rows)", csv_path, len(rows))
