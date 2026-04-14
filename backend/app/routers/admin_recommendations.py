"""
Admin Recommendation Explain Endpoint

GET /api/v1/admin/recommendations/explain/{user_id}

Returns a complete diagnostic breakdown of how the recommendation engine
scored movies for a specific user. Admin-only. Never exposed to normal users.

Designed for thesis defense demonstration:
  - Shows every user interaction and its calculated weight
  - Shows every recommended movie's cosine similarity score
  - Shows the human-readable factors that contributed to each recommendation
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from .. import database
from ..routers.auth import get_current_admin_user
from ..services.recommendation.explainer_admin import explain_recommendations
from ..models.user import User

router = APIRouter(
    prefix="/api/v1/admin/recommendations",
    tags=["admin_recommendations"],
)


@router.get("/explain/{user_id}")
def explain_user_recommendations(
    user_id: UUID,
    top_n: int = Query(10, ge=1, le=50, description="Number of top recommendations to explain"),
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),   # ← admin-only guard
):
    """
    **Admin-only diagnostic endpoint.**

    Runs the recommendation engine for `user_id` and returns a fully
    transparent JSON payload showing:

    - `user_context` — every rating, favorite, and watch event that shaped
      the user's preference vector, with each signal's calculated weight
      and a human-readable breakdown of the weighting formula.

    - `weight_summary` — aggregate statistics about the user's profile.

    - `top_recommendations` — the top-N recommended movies ranked by cosine
      similarity, each with a list of `contributing_factors` explaining
      *why* that movie scored highly.

    - `algorithm_summary` — a plain-English description of the algorithm
      pipeline for use on slides / in a thesis defense.

    This endpoint does NOT affect the normal user-facing `/recommendations/me`
    endpoint in any way.
    """
    # Verify the target user actually exists and give a clean 404
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found.",
        )

    result = explain_recommendations(db, user_id, top_n=top_n)

    # Propagate service-layer errors as 500 with detail message
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result
