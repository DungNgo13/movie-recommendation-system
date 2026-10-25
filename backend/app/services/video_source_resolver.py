"""
Video source resolver for FFmpeg / HLS processing pipeline.

Safely resolves source video files for both 'local' and 'r2' storage types:
  * 'local': validates that the local source file exists on disk.
             Never deletes or moves the original file.
  * 'r2': reads the server-side source_object_key, downloads the object to an
          isolated temporary directory using R2StorageService.download_to_path,
          verifies file existence and non-zero size, and guarantees that all
          temporary files are completely cleaned up in a finally block
          (including after failures, exceptions, and cancellations).

Never leaks credentials, presigned URLs, or private object keys in public responses.
Does not accept arbitrary client-supplied paths.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from ..models.movie import Movie
from .r2_storage_service import (
    R2NotConfiguredError,
    R2StorageError,
    R2StorageService,
    load_r2_storage_from_env,
)

logger = logging.getLogger(__name__)

# Base directory for temporary R2 source downloads.
# Kept inside the workspace media tree or system temp.
_TEMP_ROOT_DIR = os.path.join("media", "videos", "tmp_sources")


class SourceResolutionError(RuntimeError):
    """Raised when a video source cannot be resolved for processing."""


@dataclass(frozen=True)
class ResolvedSource:
    local_path: str
    source_storage: str
    source_identifier: str
    is_temporary: bool


def _safe_video_extension(key: str) -> str:
    """Extract a safe lowercase video extension from a filename or object key."""
    _, ext = os.path.splitext(key)
    ext_clean = ext.lower().strip()
    if ext_clean in {".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts"}:
        return ext_clean
    return ".mp4"


@contextlib.contextmanager
def resolve_video_source(
    movie: Movie,
    storage: Optional[R2StorageService] = None,
    temp_dir_base: Optional[str] = None,
    exists_fn: Optional[Callable[[str], bool]] = None,
) -> Iterator[ResolvedSource]:
    """
    Context manager that yields a :class:`ResolvedSource` containing a valid local
    file path accessible by FFprobe and FFmpeg.

    Guarantees:
      1. For 'local' sources: yields the local file path without modifying or deleting it.
      2. For 'r2' sources: downloads the private object to an isolated temporary
         directory and cleans up the temporary files and directory unconditionally
         in a finally block.
      3. Never deletes the remote R2 object.
    """
    check_exists = exists_fn or os.path.exists
    storage_type = (movie.source_storage or "local").lower()

    if storage_type == "local":
        local_path = movie.video_source_path
        if not local_path:
            raise SourceResolutionError("No local video source path recorded for movie.")
        if not check_exists(local_path):
            raise SourceResolutionError("Source video file missing from disk.")

        yield ResolvedSource(
            local_path=local_path,
            source_storage="local",
            source_identifier=local_path,
            is_temporary=False,
        )
        return

    if storage_type == "r2":
        object_key = movie.source_object_key
        if not object_key or not object_key.strip():
            raise SourceResolutionError("Movie is configured for R2 but has no source_object_key.")

        # Obtain R2 storage service
        r2_service = storage
        if r2_service is None:
            try:
                r2_service = load_r2_storage_from_env()
            except R2NotConfiguredError as exc:
                logger.error("R2 storage is not configured: %s", exc)
                raise SourceResolutionError("R2 storage service is not configured.") from exc

        # Create isolated temporary directory
        base_dir = temp_dir_base or _TEMP_ROOT_DIR
        os.makedirs(base_dir, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix=f"movsug_r2_{movie.id}_", dir=base_dir)

        ext = _safe_video_extension(object_key)
        safe_temp_filename = f"source_{uuid.uuid4().hex[:12]}{ext}"
        dest_path = os.path.join(temp_dir, safe_temp_filename)

        logger.info(
            "[SourceResolver] Downloading R2 source for movie %s (key=%s) to temporary path",
            movie.id, object_key
        )

        try:
            try:
                bytes_downloaded = r2_service.download_to_path(object_key, dest_path)
            except R2StorageError as exc:
                logger.error("[SourceResolver] Failed to download R2 object for movie %s: %s", movie.id, exc)
                raise SourceResolutionError(f"Failed to download source from R2 storage: {exc}") from exc

            if not os.path.isfile(dest_path):
                raise SourceResolutionError("Downloaded temporary source file does not exist.")

            actual_size = os.path.getsize(dest_path)
            if actual_size == 0 or bytes_downloaded == 0:
                raise SourceResolutionError("Downloaded temporary source file is empty (0 bytes).")

            logger.info(
                "[SourceResolver] Successfully downloaded R2 source for movie %s (%d bytes)",
                movie.id, actual_size
            )

            yield ResolvedSource(
                local_path=dest_path,
                source_storage="r2",
                source_identifier=object_key,
                is_temporary=True,
            )

        finally:
            # Guarantee thorough cleanup of the isolated directory and all contents
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info("[SourceResolver] Cleaned up temporary directory %s", temp_dir)
                except Exception as exc:
                    logger.warning("[SourceResolver] Could not remove temp dir %s: %s", temp_dir, exc)

        return

    raise SourceResolutionError(f"Unsupported source storage type '{storage_type}'.")
