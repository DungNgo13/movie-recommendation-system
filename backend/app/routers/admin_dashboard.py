from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import database
from ..models.movie import Movie
from ..models.user import User
from ..models.user_favorite import UserFavorite
from ..models.rating import Rating
from ..models.watch_history import WatchHistory
from ..schemas.admin import AdminDashboardSchema
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/dashboard",
    tags=["admin_dashboard"],
)

@router.get("", response_model=AdminDashboardSchema)
def get_dashboard_metrics(
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get summary metrics for the admin dashboard. Only accessible by admins.
    """
    return {
        "total_movies": db.query(Movie).count(),
        "total_users": db.query(User).count(),
        "total_admins": db.query(User).filter(User.role == "admin").count(),
        "total_favorites": db.query(UserFavorite).count(),
        "total_ratings": db.query(Rating).count(),
        "total_watch_history": db.query(WatchHistory).count(),
    }
