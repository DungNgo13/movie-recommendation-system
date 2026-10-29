"""Configuration settings for the Test & Evaluation Center.

Provides dataclass-based settings with auto-detection of project
structure from the current working directory.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TECSettings:
    """Central settings for the Test & Evaluation Center.

    Attributes:
        project_root: Root directory of the movie-recommendation-system project.
        backend_dir: Path to the backend (FastAPI) directory.
        frontend_dir: Path to the frontend (React/TypeScript) directory.
        backend_venv: Path to the backend virtual environment.
        reports_dir: Path to TEC-generated reports.
        artifacts_dir: Path to TEC-generated artifacts.
        experiment_reports_dir: Path to existing experiment reports.
        audit_docs_dir: Path to audit documentation.
        allow_live_r2: Whether to allow live Cloudflare R2 operations.
        allow_load_test: Whether to allow load testing.
        allow_zap_scan: Whether to allow ZAP security scanning.
        load_test_target: Target URL for load tests.
        zap_target: Target URL for ZAP scans.
    """

    project_root: Path
    backend_dir: Path
    frontend_dir: Path
    backend_venv: Path
    reports_dir: Path
    artifacts_dir: Path
    experiment_reports_dir: Path
    audit_docs_dir: Path

    # Safety defaults — destructive / network-heavy operations are off
    allow_live_r2: bool = False
    allow_load_test: bool = False
    allow_zap_scan: bool = False
    load_test_target: str = ""
    zap_target: str = ""

    @classmethod
    def auto_detect(cls) -> TECSettings:
        """Auto-detect settings from the current working directory.

        Walks up from *cwd* looking for a directory that contains both
        ``backend/`` and ``frontend/`` sub-directories. If a
        ``PROJECT_RULES.md`` file exists alongside them the match is
        considered authoritative; otherwise the first candidate is used.

        Returns:
            A fully populated :class:`TECSettings` instance.

        Raises:
            FileNotFoundError: If the project root cannot be located.
        """
        cwd = Path.cwd().resolve()
        candidate: Path | None = None

        search = cwd
        for _ in range(10):  # at most 10 levels up
            if (search / "backend").is_dir() and (search / "frontend").is_dir():
                candidate = search
                if (search / "PROJECT_RULES.md").is_file():
                    break  # authoritative match
            parent = search.parent
            if parent == search:
                break
            search = parent

        if candidate is None:
            raise FileNotFoundError(
                "Cannot auto-detect project root. Ensure you run from within "
                "the movie-recommendation-system tree."
            )

        project_root = candidate
        logger.info("Detected project root: %s", project_root)

        return cls._from_project_root(project_root)

    @classmethod
    def from_root(cls, project_root: Path) -> TECSettings:
        """Create settings from an explicit project root path."""
        return cls._from_project_root(Path(project_root).resolve())

    @classmethod
    def _from_project_root(cls, project_root: Path) -> TECSettings:
        backend_dir = project_root / "backend"
        frontend_dir = project_root / "frontend"

        # Determine venv location (Windows vs Linux)
        venv_dir = backend_dir / ".venv"
        if not venv_dir.is_dir():
            venv_dir = backend_dir / "venv"

        test_center_dir = project_root / "test_center"

        return cls(
            project_root=project_root,
            backend_dir=backend_dir,
            frontend_dir=frontend_dir,
            backend_venv=venv_dir,
            reports_dir=test_center_dir / "reports",
            artifacts_dir=test_center_dir / "artifacts",
            experiment_reports_dir=backend_dir / "reports" / "experiments",
            audit_docs_dir=project_root / "docs" / "audit",
            allow_live_r2=os.getenv("TEC_ALLOW_R2", "").lower() in ("1", "true"),
            allow_load_test=os.getenv("TEC_ALLOW_LOAD_TEST", "").lower()
            in ("1", "true"),
            allow_zap_scan=os.getenv("TEC_ALLOW_ZAP", "").lower() in ("1", "true"),
            load_test_target=os.getenv("TEC_LOAD_TARGET", ""),
            zap_target=os.getenv("TEC_ZAP_TARGET", ""),
        )

    @property
    def venv_python(self) -> Path:
        """Return the path to the venv Python executable."""
        if os.name == "nt":
            return self.backend_venv / "Scripts" / "python.exe"
        return self.backend_venv / "bin" / "python"

    @property
    def npx_cmd(self) -> str:
        """Return the npx command name for the current platform."""
        return "npx.cmd" if os.name == "nt" else "npx"

    def ensure_dirs(self) -> None:
        """Create output directories if they don't exist."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
