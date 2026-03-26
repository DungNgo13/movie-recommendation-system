from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ..schemas.rating import RatingCreateSchema, RatingResponseSchema, MovieRatingSchema
from .. import database
from ..services import rating_service
from ..routers.auth import get_current_user
from ..models.user import User

router = APIRouter(
    prefix="/api/v1/ratings",
    tags=["ratings"],
)


@router.post("", response_model=RatingResponseSchema, status_code=201)
def rate_movie(
    data: RatingCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Rate a movie (create or update)."""
    return rating_service.upsert_rating(db, current_user.id, data.movie_id, data.rating)


@router.get("/me", response_model=List[RatingResponseSchema])
def get_my_ratings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all ratings by the current user."""
    return rating_service.get_user_ratings(db, current_user.id)


@router.get("/{movie_id}/me", response_model=MovieRatingSchema)
def get_my_rating_for_movie(
    movie_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get the current user's rating for a specific movie."""
    existing = rating_service.get_user_rating_for_movie(db, current_user.id, movie_id)
    return {
        "movie_id": str(movie_id),
        "rating": existing.rating if existing else None,
    }
