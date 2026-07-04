"""
Service layer for MovieAsset CRUD operations.

Provides functions for creating, querying, and filtering movie assets
based on their media_rights_status.
"""

import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.movie_asset import MovieAsset
from ..schemas.movie_asset import MovieAssetCreateSchema

logger = logging.getLogger(__name__)


def create_asset(
    db: Session,
    movie_id: UUID,
    data: MovieAssetCreateSchema,
) -> MovieAsset:
    """Create a new MovieAsset record linked to the given movie."""
    asset = MovieAsset(
        movie_id=movie_id,
        asset_type=data.asset_type,
        url=data.url,
        local_path=data.local_path,
        source_name=data.source_name,
        source_url=data.source_url,
        license_type=data.license_type,
        license_url=data.license_url,
        attribution=data.attribution,
        is_public_domain=data.is_public_domain,
        media_rights_status=data.media_rights_status,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    if data.media_rights_status == "unknown":
        logger.warning(
            "Asset created with unknown license: movie_id=%s type=%s source=%s",
            movie_id, data.asset_type, data.source_name,
        )

    return asset


def get_assets_for_movie(
    db: Session,
    movie_id: UUID,
    include_blocked: bool = False,
) -> List[MovieAsset]:
    """
    Return all assets for a movie.

    By default, assets with media_rights_status='blocked' are excluded from
    the result set (suitable for public API responses). Pass include_blocked=True
    for admin views.
    """
    query = db.query(MovieAsset).filter(MovieAsset.movie_id == movie_id)

    if not include_blocked:
        query = query.filter(MovieAsset.media_rights_status != "blocked")

    return query.order_by(MovieAsset.created_at.desc()).all()


def get_displayable_asset(
    db: Session,
    movie_id: UUID,
    asset_type: str,
) -> Optional[dict]:
    """
    Return the best displayable asset of the given type for a movie.

    - If the best asset is 'blocked', it is skipped.
    - If the best asset is 'unknown', a placeholder marker is returned.
    - Otherwise the asset data is returned as a dict.

    Returns None if no asset of that type exists.
    """
    assets = (
        db.query(MovieAsset)
        .filter(
            MovieAsset.movie_id == movie_id,
            MovieAsset.asset_type == asset_type,
        )
        .order_by(MovieAsset.created_at.desc())
        .all()
    )

    for asset in assets:
        if asset.media_rights_status == "blocked":
            continue

        result = {
            "id": str(asset.id),
            "asset_type": asset.asset_type,
            "url": asset.url,
            "source_name": asset.source_name,
            "source_url": asset.source_url,
            "license_type": asset.license_type,
            "license_url": asset.license_url,
            "attribution": asset.attribution,
            "is_public_domain": asset.is_public_domain,
            "media_rights_status": asset.media_rights_status,
        }

        if asset.media_rights_status == "unknown":
            result["_placeholder"] = True

        return result

    return None


def delete_asset(db: Session, asset_id: UUID) -> bool:
    """Delete a MovieAsset by its ID. Returns True if deleted, False if not found."""
    asset = db.query(MovieAsset).filter(MovieAsset.id == asset_id).first()
    if asset is None:
        return False
    db.delete(asset)
    db.commit()
    return True
