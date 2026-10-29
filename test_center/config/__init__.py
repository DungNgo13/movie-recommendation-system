"""Configuration package for the Test & Evaluation Center.

Exports:
    TECSettings  — project-level configuration
    RunMetadata  — per-run environment snapshot
"""
from .run_metadata import RunMetadata
from .settings import TECSettings

__all__ = ["TECSettings", "RunMetadata"]
