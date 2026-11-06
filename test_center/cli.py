"""Command-line interface for the MovSug Test & Evaluation Center.

Entry point for all TEC operations: doctor, run, import-history,
compare, and report.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _ensure_utf8_output() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows to avoid cp1252 errors."""
    if os.name == "nt" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

_BANNER = """
========================================================
    MovSug Test & Evaluation Center (TEC)
========================================================
"""


def main() -> None:
    """CLI entry point."""
    _ensure_utf8_output()
    parser = argparse.ArgumentParser(
        prog="test-center",
        description="MovSug Test & Evaluation Center — unified testing, "
        "evaluation, and regression analysis.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # doctor
    sub.add_parser("doctor", help="Check environment health.")

    # run
    run_p = sub.add_parser("run", help="Execute test suites.")
    run_p.add_argument(
        "--suite",
        choices=["functional", "recommendation", "all-safe"],
        default="all-safe",
        help="Suite to run (default: all-safe).",
    )
    run_p.add_argument("--backend-only", action="store_true")
    run_p.add_argument("--frontend-only", action="store_true")
    run_p.add_argument(
        "--with-coverage", action="store_true",
        help="Enable coverage reporting (requires pytest-cov / vitest coverage).",
    )
    run_p.add_argument(
        "--with-lint", action="store_true",
        help="Run frontend ESLint check.",
    )
    run_p.add_argument(
        "--with-build", action="store_true",
        help="Run TypeScript production build check.",
    )

    # import-history
    sub.add_parser("import-history", help="Import historical phase data.")

    # compare
    cmp_p = sub.add_parser("compare", help="Compare two runs.")
    cmp_p.add_argument("--baseline", required=True, help="Baseline run dir.")
    cmp_p.add_argument("--candidate", required=True, help="Candidate run dir.")

    # report
    rpt_p = sub.add_parser("report", help="Generate reports from a run.")
    rpt_p.add_argument("--run", required=True, help="Run directory.")
    rpt_p.add_argument(
        "--format",
        choices=["json", "markdown", "html", "all"],
        default="all",
        help="Output format (default: all).",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    print(_BANNER)

    try:
        _dispatch(args)
    except KeyboardInterrupt:
        print("\n⚠ Interrupted.")
        sys.exit(130)
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)


def _dispatch(args: argparse.Namespace) -> None:
    """Dispatch to the appropriate command handler."""
    # Lazy imports to avoid circular deps and keep startup fast
    try:
        from .config import TECSettings, RunMetadata
    except ImportError:
        from config import TECSettings, RunMetadata

    settings = TECSettings.auto_detect()

    if args.command == "doctor":
        _cmd_doctor(settings)
    elif args.command == "run":
        _cmd_run(settings, args)
    elif args.command == "import-history":
        _cmd_import_history(settings)
    elif args.command == "compare":
        _cmd_compare(settings, args)
    elif args.command == "report":
        _cmd_report(settings, args)


# ═══════════════════════════════════════════════════════════════════════════
# doctor
# ═══════════════════════════════════════════════════════════════════════════

def _cmd_doctor(settings: Any) -> None:
    """Check environment health and print status."""
    try:
        from .config import RunMetadata
    except ImportError:
        from config import RunMetadata

    print("🩺 Environment Health Check\n")

    checks: list[tuple[str, bool, str]] = []

    # Project root
    root_ok = settings.project_root.is_dir()
    checks.append(("Project root", root_ok, str(settings.project_root)))

    # Backend dir
    be_ok = settings.backend_dir.is_dir()
    checks.append(("Backend dir", be_ok, str(settings.backend_dir)))

    # Frontend dir
    fe_ok = settings.frontend_dir.is_dir()
    checks.append(("Frontend dir", fe_ok, str(settings.frontend_dir)))

    # Backend venv
    venv_ok = settings.venv_python.is_file()
    checks.append(("Backend venv Python", venv_ok, str(settings.venv_python)))

    # pytest available
    pytest_ok = False
    try:
        import subprocess
        r = subprocess.run(
            [str(settings.venv_python), "-m", "pytest", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        pytest_ok = r.returncode == 0
        checks.append(("pytest", pytest_ok, r.stdout.strip().split("\n")[0] if pytest_ok else "not found"))
    except Exception as e:
        checks.append(("pytest", False, str(e)))

    # Node.js
    node_ok = False
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
        node_ok = r.returncode == 0
        checks.append(("Node.js", node_ok, r.stdout.strip() if node_ok else "not found"))
    except Exception:
        checks.append(("Node.js", False, "not found"))

    # npm
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    try:
        r = subprocess.run([npm_cmd, "--version"], capture_output=True, text=True, timeout=10)
        npm_ok = r.returncode == 0
        checks.append(("npm", npm_ok, r.stdout.strip() if npm_ok else "not found"))
    except Exception:
        checks.append(("npm", False, "not found"))

    # vitest
    try:
        npx = settings.npx_cmd
        r = subprocess.run(
            [npx, "vitest", "--version"],
            capture_output=True, text=True, timeout=15,
            cwd=str(settings.frontend_dir),
        )
        vitest_ok = r.returncode == 0
        checks.append(("vitest", vitest_ok, r.stdout.strip() if vitest_ok else "not found"))
    except Exception:
        checks.append(("vitest", False, "not found"))

    # Experiment reports
    exp_ok = settings.experiment_reports_dir.is_dir()
    exp_count = 0
    if exp_ok:
        exp_count = sum(1 for d in settings.experiment_reports_dir.iterdir() if d.is_dir())
    checks.append(("Experiment reports", exp_ok, f"{exp_count} directories"))

    # Audit docs
    audit_ok = settings.audit_docs_dir.is_dir()
    audit_count = 0
    if audit_ok:
        audit_count = sum(1 for f in settings.audit_docs_dir.iterdir() if f.suffix == ".md")
    checks.append(("Audit docs", audit_ok, f"{audit_count} files"))

    # Print results
    max_name = max(len(c[0]) for c in checks)
    for name, ok, detail in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name:<{max_name}}  {detail}")

    print()

    # Run metadata
    meta = RunMetadata.capture(cwd=settings.project_root)
    print(f"  Git commit:  {meta.git_commit[:12]}")
    print(f"  Git dirty:   {meta.git_dirty}")
    print(f"  Python:      {meta.python_version.split()[0]}")
    print(f"  Platform:    {meta.platform_info}")
    print(f"  Environment: {meta.environment}")
    print()

    all_ok = all(c[1] for c in checks)
    if all_ok:
        print("✅ All checks passed.")
    else:
        failed = [c[0] for c in checks if not c[1]]
        print(f"⚠ {len(failed)} check(s) failed: {', '.join(failed)}")


# ═══════════════════════════════════════════════════════════════════════════
# run
# ═══════════════════════════════════════════════════════════════════════════

def _cmd_run(settings: Any, args: argparse.Namespace) -> None:
    """Execute test suites and save results."""
    try:
        from .config import RunMetadata
        from .collectors import (
            PytestCollector,
            VitestCollector,
            RecommendationCollector,
            MetadataEnrichmentCollector,
            SemanticRecommendationCollector,
            Phase8CCollector,
            Phase8DCollector,
            CollectorResult,
        )
    except ImportError:
        from config import RunMetadata
        from collectors import (
            PytestCollector,
            VitestCollector,
            RecommendationCollector,
            MetadataEnrichmentCollector,
            SemanticRecommendationCollector,
            Phase8CCollector,
            Phase8DCollector,
            CollectorResult,
        )

    settings.ensure_dirs()
    meta = RunMetadata.capture(cwd=settings.project_root)
    run_dir = settings.reports_dir / meta.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta.save(run_dir / "metadata.json")

    results: dict[str, Any] = {}
    all_tests: list[dict] = []
    start_time = time.monotonic()

    suite = args.suite

    # Functional tests
    if suite in ("functional", "all-safe"):
        if not args.frontend_only:
            print("▶ Running backend pytest...")
            pytest_col = PytestCollector(settings)
            be_result = pytest_col.run()
            results["backend_tests"] = be_result.to_dict()
            all_tests.extend(_collect_test_dicts(be_result, "backend"))
            _print_suite_result("Backend pytest", be_result)

        if not args.backend_only:
            print("▶ Running frontend vitest...")
            vitest_col = VitestCollector(settings)
            fe_result = vitest_col.run()
            results["frontend_tests"] = fe_result.to_dict()
            all_tests.extend(_collect_test_dicts(fe_result, "frontend"))
            _print_suite_result("Frontend vitest", fe_result)

    # Recommendation experiments
    if suite in ("recommendation", "all-safe"):
        print("▶ Collecting recommendation experiments...")
        rec_col = RecommendationCollector(settings)
        records = rec_col.collect_existing()
        results["recommendation"] = {
            "status": "PASS" if records else "NOT_RUN",
            "record_count": len(records),
            "records": [r.to_dict() for r in records],
        }
        print(f"  📊 Collected {len(records)} experiment records")

        print("▶ Collecting Phase 8A metadata enrichment metrics...")
        enr_col = MetadataEnrichmentCollector(settings)
        enr_res = enr_col.collect_or_run()
        results["metadata_enrichment"] = enr_res.to_dict()
        enr_meta = enr_res.metadata or {}
        if enr_meta:
            before_pct = enr_meta.get("completeness_before", {}).get("overall_completeness_ratio", 0.0) * 100
            after_pct = enr_meta.get("completeness_after", {}).get("overall_completeness_ratio", 0.0) * 100
            print(
                f"  📊 Metadata Enrichment ({enr_meta.get('evidence_type', 'unknown')}): "
                f"{enr_meta.get('total_movies_inspected', 0)} movies inspected, "
                f"completeness {before_pct:.1f}% → {after_pct:.1f}%"
            )

        print("▶ Collecting Phase 8B semantic recommendation & ablation metrics...")
        sem_col = SemanticRecommendationCollector(settings)
        sem_res = sem_col.collect_or_run()
        results["semantic_recommendation"] = sem_res.to_dict()
        sem_meta = sem_res.metadata or {}
        if sem_meta:
            cond_a = sem_meta.get("condition_a_variants", {})
            print(
                f"  📊 Phase 8B Semantic Evaluation: {len(cond_a)} Condition A variants + "
                f"2×2 Metadata Ablation collected"
            )

        print("▶ Collecting Phase 8C MovieLens-TMDB mapping & re-evaluation metrics...")
        p8c_col = Phase8CCollector(settings)
        p8c_res = p8c_col.collect_or_run()
        results["phase8c_research"] = p8c_res.to_dict()
        p8c_meta = p8c_res.metadata or {}
        if p8c_meta:
            print(
                f"  📊 Phase 8C Research: {p8c_res.tests_passed}/{p8c_res.tests_total} artifacts collected"
            )

        print("▶ Collecting Phase 8D controlled live TMDB pilot metrics...")
        p8d_col = Phase8DCollector(settings)
        p8d_res = p8d_col.collect_or_run()
        results["phase8d_pilot"] = p8d_res.to_dict()
        p8d_meta = p8d_res.metadata or {}
        if p8d_meta:
            q_sum = p8d_meta.get("data_quality", {}).get("summary", {})
            print(
                f"  📊 Phase 8D Pilot: mode={q_sum.get('verification_mode', 'NOT_RUN')}, "
                f"requests={q_sum.get('total_requests', 0)}/{q_sum.get('request_budget', 74)}"
            )

    # Optional: Coverage reporting
    coverage_data: dict[str, Any] = {}
    with_coverage = getattr(args, "with_coverage", False)
    if with_coverage and suite in ("functional", "all-safe"):
        coverage_data = _run_coverage(settings, args, run_dir)

    # Optional: ESLint check
    lint_data: dict[str, Any] = {}
    with_lint = getattr(args, "with_lint", False)
    if with_lint:
        lint_data = _run_eslint(settings)

    # Optional: TypeScript build check
    build_data: dict[str, Any] = {}
    with_build = getattr(args, "with_build", False)
    if with_build:
        build_data = _run_tsc_build(settings)

    total_time = time.monotonic() - start_time

    # Build report data
    report_data = _build_report_data(meta, results, all_tests)
    report_data["duration_seconds"] = total_time
    if coverage_data:
        report_data["coverage"] = coverage_data
    if lint_data:
        report_data["lint"] = lint_data
    if build_data:
        report_data["build_check"] = build_data

    # Save summary
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"\n📁 Results saved to: {run_dir}")
    print(f"⏱ Total time: {total_time:.1f}s")
    print(f"📋 Run ID: {meta.run_id}")

    # Exit with non-zero code when any test has failed (Bug #5 fix)
    if report_data["overall_status"] in ("FAIL", "ERROR"):
        sys.exit(1)


def _collect_test_dicts(result: Any, prefix: str) -> list[dict]:
    """Convert CollectorResult test_cases into serialisable dicts.

    Uses the full ``test_cases`` list (all statuses), falling back to
    ``failures`` only for legacy collectors that don't populate it.
    """
    # Prefer the complete test_cases list (Bug #1 fix)
    if hasattr(result, "test_cases") and result.test_cases:
        return [
            {
                "name": tc.name,
                "classname": tc.classname,
                "status": tc.status,
                "duration_seconds": tc.duration_seconds,
                "message": tc.message or "",
                "source": tc.source or prefix,
            }
            for tc in result.test_cases
        ]

    # Legacy fallback: only failures available
    tests: list[dict] = []
    for f in result.failures:
        tests.append({
            "name": f.get("name", "unknown"),
            "classname": f.get("classname", prefix),
            "status": "FAILED",
            "duration_seconds": 0.0,
            "message": f.get("message", ""),
            "source": prefix,
        })
    return tests


def _print_suite_result(label: str, result: Any) -> None:
    """Print a summary line for a test suite result."""
    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "NOT_RUN": "⊘"}.get(
        result.status, "❓"
    )
    print(
        f"  {icon} {label}: {result.tests_passed}/{result.tests_total} passed "
        f"({result.tests_failed} failed, {result.tests_skipped} skipped) "
        f"[{result.duration_seconds:.1f}s]"
    )


def _run_coverage(
    settings: Any, args: argparse.Namespace, run_dir: Path,
) -> dict[str, Any]:
    """Run pytest-cov and vitest coverage, return combined coverage data."""
    import subprocess

    coverage_result: dict[str, Any] = {}

    # Backend coverage with pytest-cov
    if not getattr(args, "frontend_only", False):
        print("▶ Running backend coverage (pytest-cov)...")
        cov_json = settings.artifacts_dir / "backend-coverage.json"
        cmd = [
            str(settings.venv_python), "-m", "pytest",
            f"--cov=app",
            f"--cov-report=json:{cov_json}",
            "--cov-report=term:skip-covered",
            "--tb=no", "-q", "--no-header",
        ]
        try:
            proc = subprocess.run(
                cmd, cwd=str(settings.backend_dir),
                capture_output=True, text=True, timeout=600,
            )
            if cov_json.is_file():
                cov_data = json.loads(cov_json.read_text(encoding="utf-8"))
                totals = cov_data.get("totals", {})
                coverage_result["backend"] = {
                    "line_rate": round(totals.get("percent_covered", 0) / 100, 4),
                    "covered_lines": totals.get("covered_lines", 0),
                    "missing_lines": totals.get("missing_lines", 0),
                    "num_statements": totals.get("num_statements", 0),
                    "artifact": str(cov_json),
                }
                pct = totals.get("percent_covered", 0)
                print(f"  📊 Backend coverage: {pct:.1f}%")
            else:
                coverage_result["backend"] = {
                    "error": "coverage JSON not produced",
                    "returncode": proc.returncode,
                }
                print("  ⚠ Backend coverage JSON not produced")
        except Exception as exc:
            coverage_result["backend"] = {"error": str(exc)}
            print(f"  ⚠ Backend coverage failed: {exc}")

    # Frontend coverage with vitest
    if not getattr(args, "backend_only", False):
        print("▶ Running frontend coverage (vitest)...")
        npx = settings.npx_cmd
        cmd = [npx, "vitest", "run", "--coverage"]
        try:
            proc = subprocess.run(
                cmd, cwd=str(settings.frontend_dir),
                capture_output=True, text=True, timeout=300,
            )
            # vitest coverage writes to coverage/ directory
            fe_cov_json = settings.frontend_dir / "coverage" / "coverage-summary.json"
            if fe_cov_json.is_file():
                cov_data = json.loads(fe_cov_json.read_text(encoding="utf-8"))
                totals = cov_data.get("total", {})
                lines = totals.get("lines", {})
                coverage_result["frontend"] = {
                    "line_rate": round(lines.get("pct", 0) / 100, 4),
                    "covered_lines": lines.get("covered", 0),
                    "total_lines": lines.get("total", 0),
                    "artifact": str(fe_cov_json),
                }
                print(f"  📊 Frontend coverage: {lines.get('pct', 0):.1f}%")
            else:
                coverage_result["frontend"] = {
                    "status": "unavailable",
                    "note": "Coverage provider may not be installed "
                            "(install @vitest/coverage-v8).",
                    "returncode": proc.returncode,
                }
                print("  ⚠ Frontend coverage unavailable (need @vitest/coverage-v8)")
        except Exception as exc:
            coverage_result["frontend"] = {"error": str(exc)}
            print(f"  ⚠ Frontend coverage failed: {exc}")

    return coverage_result


def _run_eslint(settings: Any) -> dict[str, Any]:
    """Run ESLint on the frontend and return structured results."""
    import subprocess

    print("▶ Running frontend ESLint...")
    npx = settings.npx_cmd
    cmd = [npx, "eslint", ".", "--format", "json"]

    try:
        proc = subprocess.run(
            cmd, cwd=str(settings.frontend_dir),
            capture_output=True, text=True, timeout=120,
        )
        # ESLint exits 0 for clean, 1 for lint errors, 2 for fatal
        result: dict[str, Any] = {"returncode": proc.returncode}

        if proc.stdout.strip():
            try:
                lint_output = json.loads(proc.stdout)
                total_errors = sum(f.get("errorCount", 0) for f in lint_output)
                total_warnings = sum(f.get("warningCount", 0) for f in lint_output)
                files_with_issues = sum(
                    1 for f in lint_output
                    if f.get("errorCount", 0) + f.get("warningCount", 0) > 0
                )
                result.update({
                    "status": "PASS" if total_errors == 0 else "FAIL",
                    "errors": total_errors,
                    "warnings": total_warnings,
                    "files_checked": len(lint_output),
                    "files_with_issues": files_with_issues,
                })
                icon = "✅" if total_errors == 0 else "❌"
                print(
                    f"  {icon} ESLint: {total_errors} errors, "
                    f"{total_warnings} warnings across {len(lint_output)} files"
                )
            except json.JSONDecodeError:
                result["status"] = "ERROR"
                result["error"] = "Could not parse ESLint JSON output"
                print("  ⚠ ESLint: could not parse JSON output")
        else:
            result["status"] = "PASS" if proc.returncode == 0 else "ERROR"
            if proc.returncode != 0:
                result["stderr"] = proc.stderr[-1000:] if proc.stderr else ""
            icon = "✅" if proc.returncode == 0 else "❌"
            print(f"  {icon} ESLint: exit code {proc.returncode}")

        return result
    except Exception as exc:
        print(f"  ⚠ ESLint failed: {exc}")
        return {"status": "ERROR", "error": str(exc)}


def _run_tsc_build(settings: Any) -> dict[str, Any]:
    """Run TypeScript type-check (tsc --noEmit) and return results."""
    import subprocess

    print("▶ Running TypeScript build check...")
    npx = settings.npx_cmd
    cmd = [npx, "tsc", "--noEmit"]

    try:
        proc = subprocess.run(
            cmd, cwd=str(settings.frontend_dir),
            capture_output=True, text=True, timeout=120,
        )
        error_count = 0
        if proc.stdout:
            # Count TS error lines (format: "file.ts(line,col): error TS...")
            error_count = sum(
                1 for line in proc.stdout.splitlines()
                if ": error TS" in line
            )

        status = "PASS" if proc.returncode == 0 else "FAIL"
        icon = "✅" if proc.returncode == 0 else "❌"
        print(f"  {icon} TypeScript: {error_count} errors (exit {proc.returncode})")

        result: dict[str, Any] = {
            "status": status,
            "returncode": proc.returncode,
            "error_count": error_count,
        }
        if error_count > 0 and proc.stdout:
            # Include first 20 errors for debugging
            error_lines = [
                l for l in proc.stdout.splitlines() if ": error TS" in l
            ][:20]
            result["errors_sample"] = error_lines

        return result
    except Exception as exc:
        print(f"  ⚠ TypeScript build check failed: {exc}")
        return {"status": "ERROR", "error": str(exc)}


def _build_report_data(
    meta: Any,
    results: dict[str, Any],
    all_tests: list[dict],
) -> dict[str, Any]:
    """Build a consolidated report data dict."""
    be = results.get("backend_tests", {})
    fe = results.get("frontend_tests", {})

    be_total = be.get("tests_total", 0)
    fe_total = fe.get("tests_total", 0)
    be_passed = be.get("tests_passed", 0)
    fe_passed = fe.get("tests_passed", 0)
    be_failed = be.get("tests_failed", 0)
    fe_failed = fe.get("tests_failed", 0)
    be_skipped = be.get("tests_skipped", 0)
    fe_skipped = fe.get("tests_skipped", 0)

    total = be_total + fe_total
    passed = be_passed + fe_passed
    failed = be_failed + fe_failed
    skipped = be_skipped + fe_skipped

    # Determine overall status
    if failed > 0 or be.get("status") == "ERROR" or fe.get("status") == "ERROR":
        overall = "FAIL"
    elif total == 0:
        overall = "NOT_RUN"
    else:
        overall = "PASS"

    # Extract rec metrics for report
    rec = results.get("recommendation", {})
    rec_metrics: dict[str, Any] = {}
    if rec.get("records"):
        # Use the last record as the "current" metrics
        last_rec = rec["records"][-1]
        rec_metrics = {
            "by_k": last_rec.get("metrics_by_k", {}),
            "latency": last_rec.get("latency", {}),
            "dataset_checksum": last_rec.get("dataset_checksum", ""),
            "split_checksum": last_rec.get("split_checksum", ""),
        }

    # Extract metadata enrichment metrics (Phase 8A)
    enr = results.get("metadata_enrichment", {})
    enr_meta = enr.get("metadata", {}) if isinstance(enr, dict) else {}

    # Extract semantic recommendation metrics (Phase 8B)
    sem = results.get("semantic_recommendation", {})
    sem_meta = sem.get("metadata", {}) if isinstance(sem, dict) else {}
    sem_variants = sem_meta.get("condition_a_variants", {}) if isinstance(sem_meta, dict) else {}

    # Extract Phase 8C and Phase 8D metrics
    p8c = results.get("phase8c_research", {})
    p8c_meta = p8c.get("metadata", {}) if isinstance(p8c, dict) else {}

    p8d = results.get("phase8d_pilot", {})
    p8d_meta = p8d.get("metadata", {}) if isinstance(p8d, dict) else {}
    p8d_summary = p8d_meta.get("data_quality", {}).get("summary", {}) if isinstance(p8d_meta, dict) else {}

    return {
        "metadata": meta.to_dict(),
        "overall_status": overall,
        "summary": {
            "functional": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "status": overall,
            },
            "backend_tests": {
                "total": be_total,
                "passed": be_passed,
                "failed": be_failed,
                "skipped": be_skipped,
                "status": be.get("status", "NOT_RUN"),
            },
            "frontend_tests": {
                "total": fe_total,
                "passed": fe_passed,
                "failed": fe_failed,
                "skipped": fe_skipped,
                "status": fe.get("status", "NOT_RUN"),
            },
            "recommendations": {
                "status": rec.get("status", "NOT_RUN"),
                "algorithm": "TF-IDF v1.1 + MMR + Semantic Embeddings" if sem_variants else ("TF-IDF v1.1 + MMR" if rec.get("records") else "—"),
                "record_count": rec.get("record_count", 0) + len(sem_variants),
            },
            "metadata_enrichment": {
                "status": enr.get("status", "NOT_RUN"),
                "evidence_type": enr_meta.get("evidence_type", "—"),
                "total_movies_inspected": enr_meta.get("total_movies_inspected", 0),
                "completeness_before": enr_meta.get("completeness_before", {}).get(
                    "overall_completeness_ratio", 0.0
                ),
                "completeness_after": enr_meta.get("completeness_after", {}).get(
                    "overall_completeness_ratio", 0.0
                ),
                "admin_approval_rate": enr_meta.get("admin_approval_rate", 0.0),
                "successful_cache_refreshes": enr_meta.get("successful_cache_refreshes", 0),
            },
            "semantic_recommendation": {
                "status": sem.get("status", "NOT_RUN"),
                "condition_a_variants_count": len(sem_variants),
                "dataset_checksum": sem_meta.get("dataset_checksum", ""),
                "split_checksum": sem_meta.get("split_checksum", ""),
            },
            "phase8d_pilot": {
                "status": p8d.get("status", "NOT_RUN"),
                "pilot_size": p8d_summary.get("pilot_size", 0),
                "verification_mode": p8d_summary.get("verification_mode", "NOT_RUN"),
                "is_live": p8d_summary.get("is_live", False),
                "total_requests": p8d_summary.get("total_requests", 0),
                "request_budget": p8d_summary.get("request_budget", 74),
                "blocker_code": p8d_summary.get("blocker_code", ""),
            },
            "security": {
                "total_findings": 0,
                "critical": 0,
                "high": 0,
            },
        },
        "functional_tests": all_tests,
        "recommendation_metrics": rec_metrics,
        "metadata_enrichment": enr_meta,
        "semantic_recommendation": sem_meta,
        "phase8c_research": p8c_meta,
        "phase8d_pilot": p8d_meta,
        "known_limitations": [
            "Security scanning tools not installed (pip-audit, bandit, npm audit).",
            "Load testing requires explicit TEC_ALLOW_LOAD_TEST=1.",
            "Frontend tests may require npm install in frontend/.",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# import-history
# ═══════════════════════════════════════════════════════════════════════════

def _cmd_import_history(settings: Any) -> None:
    """Import historical phase data."""
    try:
        from .collectors import HistoryCollector
    except ImportError:
        from collectors import HistoryCollector

    settings.ensure_dirs()
    collector = HistoryCollector(settings)
    result = collector.collect()

    records = result.metadata.get("historical_records", [])
    print(f"📚 Imported {len(records)} historical records\n")

    # Print table
    if records:
        print(f"  {'Phase':<45} {'Evidence':<16} {'Status':<12}")
        print(f"  {'─' * 45} {'─' * 16} {'─' * 12}")
        for rec in records:
            phase = rec.get("phase", "—")[:44]
            evidence = rec.get("evidence_type", "—")
            status = rec.get("validation_status", "—")
            print(f"  {phase:<45} {evidence:<16} {status:<12}")

    # Save
    history_dir = settings.reports_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    out_path = history_dir / "history.json"
    out_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\n📁 Saved to: {out_path}")


# ═══════════════════════════════════════════════════════════════════════════
# compare
# ═══════════════════════════════════════════════════════════════════════════

def _cmd_compare(settings: Any, args: argparse.Namespace) -> None:
    """Compare baseline and candidate runs."""
    try:
        from .comparisons import RegressionAnalyzer
    except ImportError:
        from comparisons import RegressionAnalyzer

    baseline_dir = Path(args.baseline).resolve()
    candidate_dir = Path(args.candidate).resolve()

    b_summary = baseline_dir / "summary.json"
    c_summary = candidate_dir / "summary.json"

    if not b_summary.is_file():
        print(f"❌ Baseline summary not found: {b_summary}")
        sys.exit(1)
    if not c_summary.is_file():
        print(f"❌ Candidate summary not found: {c_summary}")
        sys.exit(1)

    b_data = json.loads(b_summary.read_text(encoding="utf-8"))
    c_data = json.loads(c_summary.read_text(encoding="utf-8"))

    analyzer = RegressionAnalyzer(b_data, c_data)
    comparison = analyzer.compare()

    # Print results
    verdict = comparison["overall_verdict"]
    icons = {"IMPROVED": "🟢", "DEGRADED": "🔴", "STABLE": "🟡", "NOT_COMPARABLE": "⚪"}
    icon = icons.get(verdict, "❓")

    print(f"📊 Comparison Result: {icon} {verdict}\n")

    if not comparison["comparable"]:
        print(f"  ⚠ {comparison['not_comparable_reason']}")
        return

    func = comparison["functional_diff"]
    if func:
        delta = func.get("pass_rate_delta", 0)
        print(f"  Pass rate: {func['pass_rate_baseline']:.1%} → {func['pass_rate_candidate']:.1%} (Δ {delta:+.1%})")
        if func.get("regressions"):
            print(f"  🔴 Regressions: {len(func['regressions'])}")
            for r in func["regressions"]:
                print(f"     - {r['name']}: {r['baseline_status']} → {r['candidate_status']}")
        if func.get("fixes"):
            print(f"  🟢 Fixes: {len(func['fixes'])}")
            for f in func["fixes"]:
                print(f"     - {f['name']}: {f['baseline_status']} → {f['candidate_status']}")

    # Save comparison
    settings.ensure_dirs()
    cmp_dir = settings.reports_dir / "comparisons"
    cmp_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = cmp_dir / f"comparison-{ts}.json"
    out_path.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\n📁 Comparison saved to: {out_path}")


# ═══════════════════════════════════════════════════════════════════════════
# report
# ═══════════════════════════════════════════════════════════════════════════

def _cmd_report(settings: Any, args: argparse.Namespace) -> None:
    """Generate reports from a TEC run."""
    try:
        from .reporting import (
            generate_json_report,
            generate_markdown_report,
            generate_vietnamese_summary,
            generate_html_report,
        )
    except ImportError:
        from reporting import (
            generate_json_report,
            generate_markdown_report,
            generate_vietnamese_summary,
            generate_html_report,
        )

    run_dir = Path(args.run).resolve()
    summary_path = run_dir / "summary.json"

    if not summary_path.is_file():
        print(f"❌ Run summary not found: {summary_path}")
        sys.exit(1)

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    fmt = args.format

    if fmt in ("json", "all"):
        p = generate_json_report(data, run_dir / "report" / "summary.json")
        print(f"  📄 JSON:     {p}")

    if fmt in ("markdown", "all"):
        p = generate_markdown_report(data, run_dir / "report" / "report.md")
        print(f"  📝 Markdown: {p}")
        # Vietnamese executive summary
        p_vi = generate_vietnamese_summary(data, run_dir / "report" / "bao_cao_tom_tat.md")
        print(f"  📝 Tóm tắt:  {p_vi}")

    if fmt in ("html", "all"):
        p = generate_html_report(data, run_dir / "report" / "report.html")
        print(f"  🌐 HTML:     {p}")

    print("\n✅ Reports generated.")


# ═══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # When run directly, add project root to sys.path and use package import
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Re-import as package to enable relative imports
    import importlib
    mod = importlib.import_module("test_center.cli")
    mod.main()
