"""Base types for test result collectors.

All collectors produce :class:`CollectorResult` instances that can be
serialised to JSON and consumed by the reporting layer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class CollectorResult:
    """Normalised output from a test collector.

    Attributes:
        suite_name: Human-readable name of the test suite.
        status: Roll-up verdict — ``PASS``, ``FAIL``, ``ERROR``,
            ``SKIPPED``, or ``NOT_RUN``.
        tests_total: Total number of tests discovered.
        tests_passed: Tests that passed.
        tests_failed: Tests with assertion failures.
        tests_errors: Tests with unexpected errors.
        tests_skipped: Tests that were skipped.
        duration_seconds: Wall-clock duration of the run.
        pass_rate: Fraction of tests that passed (0.0–1.0).
        failures: List of dicts describing individual failures.
        metadata: Additional collector-specific metadata.
        artifacts: File paths to generated artifacts (logs, XML, etc.).
    """

    suite_name: str
    status: str  # "PASS" | "FAIL" | "ERROR" | "SKIPPED" | "NOT_RUN"
    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_errors: int = 0
    tests_skipped: int = 0
    duration_seconds: float = 0.0
    pass_rate: float = 0.0
    failures: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return asdict(self)

    @staticmethod
    def not_run(suite_name: str, reason: str = "") -> CollectorResult:
        """Create a :class:`CollectorResult` for a suite that was not run."""
        return CollectorResult(
            suite_name=suite_name,
            status="NOT_RUN",
            metadata={"reason": reason} if reason else {},
        )
