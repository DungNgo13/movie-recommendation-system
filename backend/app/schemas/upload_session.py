"""
Pydantic schemas for direct-to-R2 source-video upload sessions.
"""

import os
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Allow-list of source-video MIME types accepted for direct R2 upload.
# Maps content type → object-key file extension.
ALLOWED_VIDEO_CONTENT_TYPES: Dict[str, str] = {
    "video/mp4": "mp4",
    "video/x-matroska": "mkv",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "video/x-msvideo": "avi",
}


class UploadSessionCreateSchema(BaseModel):
    """Request body for initiating a direct R2 upload."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    size: int = Field(..., gt=0, description="Declared file size in bytes")

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        # Keep only the base name; the filename is stored for display only and
        # is NEVER used to build the object key.
        name = os.path.basename(v.replace("\\", "/")).strip()
        if not name or name in {".", ".."}:
            raise ValueError("filename must not be empty")
        return name

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ALLOWED_VIDEO_CONTENT_TYPES:
            raise ValueError(
                "content_type must be one of: "
                + ", ".join(sorted(ALLOWED_VIDEO_CONTENT_TYPES))
            )
        return normalized


class UploadSessionSchema(BaseModel):
    """Admin-facing view of an upload session (object key is not exposed)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movie_id: UUID
    status: str
    original_filename: Optional[str] = None
    content_type: str
    expected_size: int
    actual_size: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    completed_at: Optional[datetime] = None


class UploadSessionCreateResponseSchema(BaseModel):
    """
    Response for upload initiation.  ``upload_url`` is a short-lived secret
    capability: clients must use it once and must not log or store it.
    """
    session: UploadSessionSchema
    upload_url: str
    upload_method: str = "PUT"
    upload_headers: Dict[str, str]
    expires_in_seconds: int
