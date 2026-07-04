"""
REST endpoints for per-movie asset management.

Public:  GET  /api/v1/movies/{movie_id}/assets
Admin:   POST /api/v1/movies/{movie_id}/assets
Admin:   DELETE /api/v1/movies/{movie_id}/assets/{asset_id}
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from .. import database
from ..schemas.movie_asset import (
    MovieAssetSchema,
    MovieAssetCreateSchema,
    MovieAssetListSchema,
)
from ..services import asset_license_service
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/movies/{movie_id}/assets",
    tags=["movie-assets"],
)


@router.get("", response_model=MovieAssetListSchema)
def list_assets(
    movie_id: UUID,
    db: Session = Depends(database.get_db),
):
    """List all displayable assets for a movie (blocked assets excluded)."""
    assets = asset_license_service.get_assets_for_movie(db, movie_id)
    return {"items": assets, "total": len(assets)}


@router.post("", response_model=MovieAssetSchema, status_code=201)
def create_asset(
    movie_id: UUID,
    data: MovieAssetCreateSchema,
    db: Session = Depends(database.get_db),
    _admin=Depends(get_current_admin_user),
):
    """Create a new asset for a movie (admin only)."""
    from ..services.movie_service import get_movie

    movie = get_movie(db, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    return asset_license_service.create_asset(db, movie_id, data)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(
    movie_id: UUID,
    asset_id: UUID,
    db: Session = Depends(database.get_db),
    _admin=Depends(get_current_admin_user),
):
    """Delete an asset (admin only)."""
    deleted = asset_license_service.delete_asset(db, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
