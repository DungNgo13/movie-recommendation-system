"""
Pydantic schemas for MovieAsset CRUD operations.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from .movie import ALLOWED_MEDIA_RIGHTS
from ..models.movie_asset import ALLOWED_ASSET_TYPES


class MovieAssetSchema(BaseModel):
    """Read-only response schema for a movie asset."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movie_id: UUID
    asset_type: str
    url: Optional[str] = None
    local_path: Optional[str] = Field(None, exclude=True)  # never expose fs paths
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_type: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    is_public_domain: bool = False
    media_rights_status: str = "unknown"
    created_at: datetime


class MovieAssetCreateSchema(BaseModel):
    """Input schema for creating a movie asset."""
    asset_type: str
    url: Optional[str] = None
    local_path: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_type: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    is_public_domain: bool = False
    media_rights_status: str = "unknown"

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, v: str) -> str:
        if v not in ALLOWED_ASSET_TYPES:
            raise ValueError(
                f"asset_type must be one of: {', '.join(sorted(ALLOWED_ASSET_TYPES))}"
            )
        return v

    @field_validator("media_rights_status")
    @classmethod
    def validate_media_rights(cls, v: str) -> str:
        if v not in ALLOWED_MEDIA_RIGHTS:
            raise ValueError(
                f"media_rights_status must be one of: {', '.join(sorted(ALLOWED_MEDIA_RIGHTS))}"
            )
        return v


class MovieAssetListSchema(BaseModel):
    """Response wrapper for a list of movie assets."""
    items: List[MovieAssetSchema]
    total: int
