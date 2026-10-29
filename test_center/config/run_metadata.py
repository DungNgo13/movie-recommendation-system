"""Run metadata capture for reproducibility.

Captures git state, Python/Node versions, platform info, and tool
versions so every TEC run is fully reproducible.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_cmd(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a command and return stripped stdout, or '' on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=cwd,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


@dataclass
class RunMetadata:
    """Immutable snapshot of the environment at the time of a TEC run.

    Attributes:
        run_id: Unique identifier, e.g. ``tec-20261029-134200-abc123``.
        timestamp_utc: ISO-8601 timestamp in UTC.
        git_commit: Full SHA of the current HEAD commit.
        git_dirty: Whether the working tree has uncommitted changes.
        python_version: ``sys.version`` string.
        node_version: Node.js version string, or ``None`` if unavailable.
        platform_info: ``platform.platform()`` output.
        os_name: ``os.name`` equivalent (e.g. ``nt``, ``posix``).
        environment: Execution context — ``local``, ``ci``, or ``staging``.
        tool_versions: Mapping of tool names to their version strings.
    """

    run_id: str
    timestamp_utc: str
    git_commit: str
    git_dirty: bool
    python_version: str
    node_version: str | None
    platform_info: str
    os_name: str
    environment: str
    tool_versions: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain-dict representation suitable for JSON."""
        return asdict(self)

    def save(self, path: Path) -> None:
        """Persist metadata to a JSON file at *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Run metadata saved to %s", path)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def capture(cls, cwd: Path | None = None) -> RunMetadata:
        """Capture current environment metadata.

        Args:
            cwd: Working directory for git commands (defaults to cwd).

        Returns:
            A fully populated :class:`RunMetadata`.
        """
        import os as _os

        now = datetime.now(timezone.utc)
        git_commit = _run_cmd(["git", "rev-parse", "HEAD"], cwd=cwd) or "unknown"
        git_status = _run_cmd(["git", "status", "--porcelain"], cwd=cwd)
        git_dirty = bool(git_status)

        node_version = _run_cmd(["node", "--version"], cwd=cwd) or None

        # Detect environment
        environment = "local"
        if _os.getenv("CI"):
            environment = "ci"
        elif _os.getenv("TEC_ENV"):
            environment = _os.getenv("TEC_ENV", "local")

        # Collect tool versions
        tool_versions: dict[str, str] = {}
        pytest_ver = _run_cmd([sys.executable, "-m", "pytest", "--version"], cwd=cwd)
        if pytest_ver:
            # pytest output: "pytest 8.x.x"
            parts = pytest_ver.split()
            for i, p in enumerate(parts):
                if p == "pytest" and i + 1 < len(parts):
                    tool_versions["pytest"] = parts[i + 1]
                    break
            else:
                tool_versions["pytest"] = pytest_ver.split("\n")[0]

        npm_ver = _run_cmd(["npm", "--version"], cwd=cwd)
        if npm_ver:
            tool_versions["npm"] = npm_ver

        git_ver = _run_cmd(["git", "--version"], cwd=cwd)
        if git_ver:
            tool_versions["git"] = git_ver.replace("git version ", "")

        short_commit = git_commit[:7] if git_commit != "unknown" else "0000000"
        run_id = f"tec-{now.strftime('%Y%m%d-%H%M%S')}-{short_commit}"

        return cls(
            run_id=run_id,
            timestamp_utc=now.isoformat(),
            git_commit=git_commit,
            git_dirty=git_dirty,
            python_version=sys.version,
            node_version=node_version,
            platform_info=platform.platform(),
            os_name=_os.name,
            environment=environment,
            tool_versions=tool_versions,
        )
