"""Vitest collector — runs the frontend test suite and collects results.

Invokes ``npx vitest run`` with JUnit XML output, then parses the XML
to produce a :class:`CollectorResult`.
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


class VitestCollector:
    """Collect results from a vitest run against the frontend.

    Args:
        settings: TEC settings providing paths.
    """

    def __init__(self, settings: TECSettings) -> None:
        self._settings = settings

    def run(
        self,
        junit_xml_path: Path | None = None,
    ) -> CollectorResult:
        """Execute vitest and return collected results.

        Args:
            junit_xml_path: Where to write the JUnit XML. If ``None``,
                a temporary path inside ``artifacts_dir`` is used.

        Returns:
            A :class:`CollectorResult` summarising the run.
        """
        settings = self._settings
        frontend_dir = settings.frontend_dir

        if not (frontend_dir / "node_modules").is_dir():
            logger.error("node_modules not found in %s", frontend_dir)
            return CollectorResult.not_run(
                "frontend-vitest",
                reason=f"node_modules not found in {frontend_dir}",
            )

        settings.ensure_dirs()

        if junit_xml_path is None:
            junit_xml_path = settings.artifacts_dir / "vitest-results.xml"

        npx = settings.npx_cmd
        cmd: list[str] = [
            npx,
            "vitest",
            "run",
            f"--reporter=junit",
            f"--outputFile={junit_xml_path}",
        ]

        logger.info("Running: %s", " ".join(cmd))
        logger.info("Working directory: %s", frontend_dir)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(frontend_dir),
                capture_output=True,
                text=True,
                timeout=300,  # 5 min max
                shell=False,
            )
            duration = time.monotonic() - start
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            logger.error("vitest timed out after %.1fs", duration)
            return CollectorResult(
                suite_name="frontend-vitest",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": "vitest timed out after 300s"},
            )
        except Exception as exc:
            duration = time.monotonic() - start
            logger.exception("Failed to run vitest")
            return CollectorResult(
                suite_name="frontend-vitest",
                status="ERROR",
                duration_seconds=duration,
                metadata={"error": str(exc)},
            )

        logger.info("vitest exited with code %d (%.2fs)", proc.returncode, duration)

        # Parse JUnit XML if it exists
        if junit_xml_path.is_file():
            try:
                suite = parse_junit_xml(junit_xml_path)
            except Exception as exc:
                logger.exception("Failed to parse vitest JUnit XML")
                return CollectorResult(
                    suite_name="frontend-vitest",
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
                suite_name="frontend-vitest",
                status=status,
                tests_total=suite.tests,
                tests_passed=suite.passed,
                tests_failed=suite.failures,
                tests_errors=suite.errors,
                tests_skipped=suite.skipped,
                duration_seconds=suite.time_seconds or duration,
                pass_rate=suite.pass_rate,
                failures=failures,
                metadata={"returncode": proc.returncode},
                artifacts=[str(junit_xml_path)],
            )

        # Fallback: no XML produced
        logger.warning("No JUnit XML produced — using exit code only")
        status = "PASS" if proc.returncode == 0 else "FAIL"
        return CollectorResult(
            suite_name="frontend-vitest",
            status=status,
            duration_seconds=duration,
            metadata={
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            },
        )
