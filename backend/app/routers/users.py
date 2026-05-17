from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from ..schemas.user import UserResponseSchema
from .. import database
from ..services import avatar_service
from ..routers.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
)


@router.post("/me/avatar", response_model=UserResponseSchema)
def upload_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Upload or replace the current user's avatar image.

    Constraints:
      - File type: JPEG, PNG, or WebP only.
      - File size: ≤ 2 MB.
    """
    updated_user = avatar_service.upload_avatar(db, current_user, file)
    return updated_user
