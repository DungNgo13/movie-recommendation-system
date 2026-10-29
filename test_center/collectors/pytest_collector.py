"""Pytest collector — runs the backend test suite and collects results.

Uses the backend virtual environment's Python to invoke ``pytest``
with JUnit XML output, then parses the XML to produce a
:class:`CollectorResult`.
"""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from ..config.settings import TECSettings
from ..parsers.junit_xml import parse_junit_xml
from .base import CollectorResult

logger = logging.getLogger(__name__)


class PytestCollector:
    """Collect results from a pytest run against the backend.

    Args:
        settings: TEC settings providing paths and venv location.
    """

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    def run(
        self,
        markers: str | None = None,
        junit_xml_path: Path | None = None,
    ) -> CollectorResult:
        """Execute pytest and return collected results.

        Args:
            markers: Optional pytest marker expression (``-m``).
            junit_xml_path: Where to write the JUnit XML.  If ``None``,
                a temporary path inside ``artifacts_dir`` is used.

        Returns:
            A :class:`CollectorResult` summarising the run.
        """
        settings = self._settings
        python = settings.venv_python

        if not python.is_file():
            logger.error("Backend venv Python not found: %s", python)
            return CollectorResult.not_run(
                "backend-pytest",
                reason=f"venv python not found: {python}",
            )

        # Ensure artifacts dir exists
        settings.ensure_dirs()

        if junit_xml_path is None:
            junit_xml_path = settings.artifacts_dir / "pytest-results.xml"

        cmd: list[str] = [
            str(python),
            "-m",
            "pytest",
            f"--junitxml={junit_xml_path}",
            "--tb=short",
            "-q",
        ]

        if markers:
            cmd.extend(["-m", markers])

        logger.info("Running: %s", " ".join(cmd))
        logger.info("Working directory: %s", settings.backend_dir)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(settings.backend_dir),
                capture_output=True,
                text=True,
                timeout=600,  # 10 min max
            )
            duration = time.monotonic() - start
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            logger.error("pytest timed out after %.1fs", duration)
            return CollectorResult(
                suite_name="backend-pytest",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": "pytest timed out after 600s"},
            )
        except Exception as exc:
            duration = time.monotonic() - start
            logger.exception("Failed to run pytest")
            return CollectorResult(
                suite_name="backend-pytest",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        logger.info("pytest exited with code %d (%.2fs)", proc.returncode, duration)

        # Parse JUnit XML if it exists
        if junit_xml_path.is_file():
            try:
                suite = parse_junit_xml(junit_xml_path)
            except Exception as exc:
                logger.exception("Failed to parse JUnit XML")
                return CollectorResult(
                    suite_name="backend-pytest",
                    status="ERROR",
                    duration_seconds=duration,
                    metadata={"error": f"XML parse error: {exc}"},
                    artifacts=[str(junit_xml_path)],
                )

            failures = [
                {
                    "name": tc.name,
                    "classname": tc.classname,
                    "message": tc.message or "",
                }
                for tc in suite.test_cases
                if tc.status in ("failed", "error")
            ]

            status = "PASS" if suite.failures == 0 and suite.errors == 0 else "FAIL"

            return CollectorResult(
                suite_name="backend-pytest",
                status=status,
                tests_total=suite.tests,
                tests_passed=suite.passed,
                tests_failed=suite.failures,
                tests_errors=suite.errors,
                tests_skipped=suite.skipped,
                duration_seconds=suite.time_seconds or duration,
                pass_rate=suite.pass_rate,
                failures=failures,
                metadata={
                    "returncode": proc.returncode,
                    "markers": markers,
                },
                artifacts=[str(junit_xml_path)],
            )

        # Fallback: no XML produced
        logger.warning("No JUnit XML produced — using exit code only")
        status = "PASS" if proc.returncode == 0 else "FAIL"
        return CollectorResult(
            suite_name="backend-pytest",
            status=status,
            duration_seconds=duration,
            metadata={
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            },
        )
