"""Admin-only view of a movie's source-video storage state."""

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class MovieSourceStatusSchema(BaseModel):
    """
    Storage state for the admin UI.  Deliberately excludes the R2 object key,
    bucket, local filesystem path and any URL — only flags and statuses.
    """
    movie_id: UUID
    source_storage: Literal["local", "r2"]
    # True when the active source can actually be used (local file present on
    # disk, or a completed + verified R2 upload backs source_object_key).
    source_available: bool
    # Existing processing status column (no_video / uploaded / processing / ready / failed).
    processing_status: Optional[str] = None
    hls_ready: bool
    # False for R2 sources until the FFmpeg R2 source resolver exists.
    hls_processing_supported: bool
