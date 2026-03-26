from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from .. import database
from ..models.user import User
from ..schemas.user import UserResponseSchema, UserRoleUpdateSchema
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["admin_users"],
)

@router.get("", response_model=List[UserResponseSchema])
def get_all_users(
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get a list of all users. Only accessible by admins.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users

@router.patch("/{user_id}/role", response_model=UserResponseSchema)
def update_user_role(
    user_id: UUID,
    role_update: UserRoleUpdateSchema,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Update a user's role. Only accessible by admins.
    Role must be 'user' or 'admin'.
    """
    if role_update.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'user' or 'admin'"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Optional: Prevent admin from removing their own admin privilege to avoid locking out the only admin
    if user.id == admin_user.id and role_update.role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot revoke your own admin privileges."
        )

    user.role = role_update.role
    db.commit()
    db.refresh(user)
    return user
