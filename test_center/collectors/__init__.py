"""Collectors package for the Test & Evaluation Center.

Exports:
    CollectorResult          — normalised test-run output
    TestCaseRecord           — individual test case result
    PytestCollector          — backend pytest runner
    VitestCollector          — frontend vitest runner
    RecommendationCollector  — recommendation experiment collector
    HistoryCollector         — historical phase data collector
    MetadataEnrichmentCollector — Phase 8A enrichment benchmark collector
    SemanticRecommendationCollector — Phase 8B semantic evaluation collector
    Phase8CCollector         — Phase 8C identity mapping & enrichment re-evaluation collector
"""
from .base import CollectorResult, TestCaseRecord
from .history_collector import HistoryCollector
from .metadata_enrichment_collector import MetadataEnrichmentCollector
from .phase8c_collector import Phase8CCollector
from .pytest_collector import PytestCollector
from .recommendation_collector import RecommendationCollector
from .semantic_recommendation_collector import SemanticRecommendationCollector
from .vitest_collector import VitestCollector

__all__ = [
    "CollectorResult",
    "TestCaseRecord",
    "PytestCollector",
    "VitestCollector",
    "RecommendationCollector",
    "HistoryCollector",
    "MetadataEnrichmentCollector",
    "SemanticRecommendationCollector",
    "Phase8CCollector",
]
