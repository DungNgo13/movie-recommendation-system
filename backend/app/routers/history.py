from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ..schemas.history import HistoryItemSchema
from .. import database
from ..services import history_service
from ..routers.auth import get_current_user
from ..models.user import User

router = APIRouter(
    prefix="/api/v1/history",
    tags=["history"],
)


@router.post("/{movie_id}", status_code=201)
def record_watch(
    movie_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Record that the current user watched a movie."""
    history_service.record_watch(db, current_user.id, movie_id)
    return {"movie_id": str(movie_id), "recorded": True}


@router.get("/me", response_model=List[HistoryItemSchema])
def get_my_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get the current user's watch history, most recent first."""
    return history_service.get_user_history(db, current_user.id, limit=limit)
