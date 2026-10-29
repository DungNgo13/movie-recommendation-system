"""Collectors package for the Test & Evaluation Center.

Exports:
    CollectorResult          — normalised test-run output
    PytestCollector          — backend pytest runner
    VitestCollector          — frontend vitest runner
    RecommendationCollector  — recommendation experiment collector
    HistoryCollector         — historical phase data collector
"""
from .base import CollectorResult
from .history_collector import HistoryCollector
from .pytest_collector import PytestCollector
from .recommendation_collector import RecommendationCollector
from .vitest_collector import VitestCollector

__all__ = [
    "CollectorResult",
    "PytestCollector",
    "VitestCollector",
    "RecommendationCollector",
    "HistoryCollector",
]
