from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ..schemas.favorite import FavoriteMovieSchema, FavoriteResponseSchema, GuestFavoriteMergeSchema
from .. import database
from ..services import favorite_service
from ..routers.auth import get_current_user
from ..models.user import User

router = APIRouter(
    prefix="/api/v1/favorites",
    tags=["favorites"],
)


@router.get("/me", response_model=List[FavoriteMovieSchema])
def get_my_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all favorite movies for the current user."""
    return favorite_service.get_user_favorites(db, current_user.id)


@router.get("/me/ids", response_model=List[str])
def get_my_favorite_ids(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get just the favorite movie IDs for the current user."""
    return favorite_service.get_user_favorite_ids(db, current_user.id)


@router.post("/me/merge", status_code=200)
def merge_guest_favorites(
    payload: GuestFavoriteMergeSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Merge guest favorite movie IDs into the authenticated user's favorites."""
    merged = favorite_service.merge_guest_favorites(
        db, current_user.id, payload.movie_ids,
    )
    return {"merged": merged}


@router.post("/{movie_id}", response_model=FavoriteResponseSchema, status_code=201)
def add_favorite(
    movie_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Add a movie to favorites."""
    favorite_service.add_favorite(db, current_user.id, movie_id)
    return {"movie_id": str(movie_id), "favorited": True}


@router.delete("/{movie_id}", response_model=FavoriteResponseSchema)
def remove_favorite(
    movie_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Remove a movie from favorites."""
    favorite_service.remove_favorite(db, current_user.id, movie_id)
    return {"movie_id": str(movie_id), "favorited": False}

