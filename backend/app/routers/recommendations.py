from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from ..schemas.recommendation import RecommendedMovieSchema
from .. import database
from ..services.recommendation.engine import get_recommendations
from ..routers.auth import get_current_user
from ..models.user import User

router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["recommendations"],
)


@router.get("/me", response_model=List[RecommendedMovieSchema])
def get_my_recommendations(
    top_n: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Get personalized movie recommendations for the current user.

    Uses TF-IDF content-based filtering with cosine similarity.
    Falls back to popular movies for cold-start users.
    """
    return get_recommendations(db, current_user.id, top_n=top_n)
