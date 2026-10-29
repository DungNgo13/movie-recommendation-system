"""Parsers package for the Test & Evaluation Center.

Exports:
    parse_junit_xml          — JUnit XML → TestSuiteResult
    parse_experiment_metrics — metrics.json → ExperimentRecord
    parse_ablation_summary   — ablation_summary.json → dict of ExperimentRecord
    parse_mmr_ablation_summary — mmr_ablation_summary.json → dict of ExperimentRecord
"""
from .experiment_json import (
    ExperimentRecord,
    parse_ablation_summary,
    parse_experiment_metrics,
    parse_mmr_ablation_summary,
)
from .junit_xml import TestCase, TestSuiteResult, parse_junit_xml

__all__ = [
    "TestCase",
    "TestSuiteResult",
    "parse_junit_xml",
    "ExperimentRecord",
    "parse_experiment_metrics",
    "parse_ablation_summary",
    "parse_mmr_ablation_summary",
]
