"""JUnit XML parser for test result ingestion.

Parses the standard JUnit XML format produced by pytest (``--junitxml``)
and vitest (``--reporter=junit``) into typed dataclasses.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """A single test case extracted from JUnit XML.

    Attributes:
        name: Test function / method name.
        classname: Fully qualified class or module path.
        time_seconds: Execution duration in seconds.
        status: One of ``passed``, ``failed``, ``error``, ``skipped``.
        message: Failure/error/skip message, if any.
    """

    name: str
    classname: str
    time_seconds: float
    status: str  # "passed" | "failed" | "error" | "skipped"
    message: str | None = None


@dataclass
class TestSuiteResult:
    """Aggregated result for a single ``<testsuite>`` element.

    Attributes:
        name: Suite name.
        tests: Total number of tests in the suite.
        failures: Number of assertion failures.
        errors: Number of unexpected errors.
        skipped: Number of skipped tests.
        time_seconds: Total wall-clock time for the suite.
        test_cases: Individual :class:`TestCase` results.
    """

    name: str
    tests: int
    failures: int
    errors: int
    skipped: int
    time_seconds: float
    test_cases: list[TestCase] = field(default_factory=list)

    @property
    def passed(self) -> int:
        """Number of tests that passed."""
        return self.tests - self.failures - self.errors - self.skipped

    @property
    def pass_rate(self) -> float:
        """Fraction of tests that passed (0.0–1.0)."""
        if self.tests == 0:
            return 0.0
        return self.passed / self.tests


def _safe_float(value: str | None, default: float = 0.0) -> float:
    """Convert a string to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: str | None, default: int = 0) -> int:
    """Convert a string to int, returning *default* on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_testcase(elem: ET.Element) -> TestCase:
    """Parse a single ``<testcase>`` element."""
    name = elem.get("name", "unknown")
    classname = elem.get("classname", "")
    time_seconds = _safe_float(elem.get("time"))

    # Determine status from child elements
    failure = elem.find("failure")
    error = elem.find("error")
    skipped = elem.find("skipped")

    if failure is not None:
        status = "failed"
        message = failure.get("message", failure.text or "")
    elif error is not None:
        status = "error"
        message = error.get("message", error.text or "")
    elif skipped is not None:
        status = "skipped"
        message = skipped.get("message", skipped.text or "")
    else:
        status = "passed"
        message = None

    return TestCase(
        name=name,
        classname=classname,
        time_seconds=time_seconds,
        status=status,
        message=message,
    )


def parse_junit_xml(path: Path) -> TestSuiteResult:
    """Parse a JUnit XML file and return a :class:`TestSuiteResult`.

    Handles both single-suite files (``<testsuite>``) and multi-suite
    files (``<testsuites>`` wrapping one or more ``<testsuite>``).
    When multiple suites are present, their results are merged into
    a single :class:`TestSuiteResult`.

    Args:
        path: Path to the JUnit XML file.

    Returns:
        Parsed test suite result.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ET.ParseError: If the XML is malformed.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"JUnit XML not found: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    # Collect all <testsuite> elements
    suites: list[ET.Element] = []
    if root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    elif root.tag == "testsuite":
        suites = [root]
    else:
        logger.warning("Unexpected root element <%s> in %s", root.tag, path)
        suites = list(root.findall(".//testsuite")) or [root]

    # Merge all suites into one result
    all_cases: list[TestCase] = []
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0.0
    suite_name = ""

    for suite_elem in suites:
        if not suite_name:
            suite_name = suite_elem.get("name", "unknown")

        total_tests += _safe_int(suite_elem.get("tests"))
        total_failures += _safe_int(suite_elem.get("failures"))
        total_errors += _safe_int(suite_elem.get("errors"))
        total_skipped += _safe_int(suite_elem.get("skipped"))
        total_time += _safe_float(suite_elem.get("time"))

        for tc_elem in suite_elem.findall("testcase"):
            all_cases.append(_parse_testcase(tc_elem))

    # If no tests attribute was set, infer from parsed cases
    if total_tests == 0 and all_cases:
        total_tests = len(all_cases)
        total_failures = sum(1 for c in all_cases if c.status == "failed")
        total_errors = sum(1 for c in all_cases if c.status == "error")
        total_skipped = sum(1 for c in all_cases if c.status == "skipped")

    result = TestSuiteResult(
        name=suite_name or path.stem,
        tests=total_tests,
        failures=total_failures,
        errors=total_errors,
        skipped=total_skipped,
        time_seconds=total_time,
        test_cases=all_cases,
    )

    logger.info(
        "Parsed %s: %d tests, %d passed, %d failed, %d errors, %d skipped (%.2fs)",
        path.name,
        result.tests,
        result.passed,
        result.failures,
        result.errors,
        result.skipped,
        result.time_seconds,
    )

    return result
