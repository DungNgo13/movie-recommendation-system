# MovSug Test & Evaluation Center (TEC)

Unified test orchestration, evaluation, regression analysis, and reporting tool for the MovSug graduation project.

## Quick Start

```bash
# From project root (d:\TLTN\movie-recommendation-system)
# Using the backend venv Python:

# Check environment health
python -m test_center doctor

# Run all safe tests (backend + frontend + experiment import)
python -m test_center run --suite all-safe

# Run backend tests only
python -m test_center run --suite functional --backend-only

# Import historical experiment data
python -m test_center import-history

# Generate reports from a run
python -m test_center report --run test_center/reports/<RUN_ID> --format all

# Compare two runs
python -m test_center compare --baseline test_center/reports/<RUN_A> --candidate test_center/reports/<RUN_B>
```

## Architecture

```
test_center/
├── __init__.py              # Package root
├── __main__.py              # python -m entry point
├── cli.py                   # CLI commands (doctor, run, import-history, compare, report)
├── config/
│   ├── settings.py          # TECSettings — auto-detected project paths
│   └── run_metadata.py      # RunMetadata — git, platform, tool version snapshot
├── parsers/
│   ├── junit_xml.py         # JUnit XML parser (pytest, vitest output)
│   └── experiment_json.py   # Experiment JSON parser (metrics.json, ablation_summary.json)
├── collectors/
│   ├── base.py              # CollectorResult data class
│   ├── pytest_collector.py  # Backend pytest runner
│   ├── vitest_collector.py  # Frontend vitest runner
│   ├── recommendation_collector.py  # Experiment report scanner
│   └── history_collector.py # Phase 1-6 historical data importer
├── comparisons/
│   └── regression.py        # RegressionAnalyzer — baseline vs candidate comparison
├── reporting/
│   ├── json_report.py       # JSON + CSV + failures output
│   ├── markdown_report.py   # Thesis-ready Markdown reports
│   └── html_report.py       # Self-contained HTML dashboard (dark mode, sortable tables)
├── tests/
│   ├── conftest.py          # Shared fixtures (JUnit XML, experiment JSON, report data)
│   ├── test_parsers.py      # Parser unit tests
│   └── test_comparisons.py  # Regression analyzer unit tests
├── reports/                 # Generated reports (per-run directories)
└── artifacts/               # Generated artifacts (JUnit XML, logs)
```

## CLI Commands

### `doctor`
Checks environment health: project root, venv, pytest, Node.js, npm, vitest, experiment reports, audit docs.

### `run --suite <suite> [--backend-only] [--frontend-only]`
Execute test suites:
- `functional` — pytest + vitest
- `recommendation` — scan existing experiment reports
- `all-safe` — functional + recommendation (no destructive operations)

### `import-history`
Import Phase 1–6 historical data from experiment JSON files and audit documentation. Classifies evidence as `IMPORTED`, `NARRATIVE_ONLY`, or `EXECUTED`.

### `compare --baseline <DIR> --candidate <DIR>`
Compare two TEC runs for regressions. Detects:
- Tests that regressed (PASS → FAIL)
- Tests that were fixed (FAIL → PASS)
- Metric improvements/degradations
- Checksum mismatches (NOT_COMPARABLE verdict)

### `report --run <DIR> --format <json|markdown|html|all>`
Generate reports from a run's `summary.json`:
- **JSON**: `summary.json`, `test_results.json`, `failures.json`, `metrics.csv`
- **Markdown**: Thesis-ready report with tables and checksums
- **HTML**: Self-contained dashboard with dark mode, sortable tables, bar charts

## Safety

- Default `all-safe` suite is **non-destructive** — no live R2, no production DB, no load tests
- Live operations require explicit env vars: `TEC_ALLOW_R2=1`, `TEC_ALLOW_LOAD_TEST=1`
- Never saves credentials, JWT tokens, presigned URLs, or personal data
- Historical imports are labeled `IMPORTED`, not `EXECUTED`
- Unavailable metrics display `N/A`, not fabricated values

## Self-Tests

```bash
python -m pytest test_center/tests/ -v
```

## Dependencies

Uses Python standard library + existing project dependencies (pytest, etc.). No additional packages required.
