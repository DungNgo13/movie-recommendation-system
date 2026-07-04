"""
MovieAsset model — per-asset license and source tracking.

Each movie can have multiple assets (poster, backdrop, trailer, etc.), each with
its own license, source, and media_rights_status independently of the movie-level
metadata license.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


# Allowed asset_type values (validated at the schema level, not DB-enforced)
ALLOWED_ASSET_TYPES = {
    "poster",
    "backdrop",
    "banner",
    "trailer",
    "full_video",
    "actor_image",
    "director_image",
    "placeholder",
}


class MovieAsset(Base):
    __tablename__ = "movie_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type = Column(String(30), nullable=False)  # see ALLOWED_ASSET_TYPES

    # Where the asset lives
    url = Column(String(500), nullable=True)         # external URL (CDN, Wikimedia, etc.)
    local_path = Column(String(500), nullable=True)  # local filesystem path if downloaded

    # Source & license tracking (mirrors Movie-level fields)
    source_name = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True)
    license_type = Column(String(100), nullable=True)
    license_url = Column(String(500), nullable=True)
    attribution = Column(Text, nullable=True)
    is_public_domain = Column(Boolean, default=False, nullable=False, server_default="false")
    media_rights_status = Column(
        String(30), default="unknown", nullable=False, server_default="unknown",
    )

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_movie_assets_movie_type", "movie_id", "asset_type"),
    )
