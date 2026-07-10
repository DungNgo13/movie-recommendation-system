from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from .. import database
from ..models.user import User
from ..schemas.user import UserResponseSchema, UserRoleUpdateSchema, ForceResetPasswordSchema, UserSecurityAuditSchema
from ..core.security import hash_password
from .auth import get_current_admin_user
from ..services.admin_service import create_audit_log, check_is_last_admin

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
    # Limit to 100 for MVP production safety (ideally should be paginated)
    users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    return users


@router.get("/security-audit", response_model=List[UserSecurityAuditSchema])
def get_security_audit(
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """
    Admin-only: Get full security audit data for all users.
    Includes login tracking, failed attempts, and password change timestamps.
    """
    users = db.query(User).order_by(User.created_at.desc()).limit(200).all()
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

    # Prevent demoting the last remaining admin
    if user.role == "admin" and role_update.role == "user":
        if check_is_last_admin(db, user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last remaining admin."
            )

    old_role = user.role
    user.role = role_update.role
    db.commit()
    db.refresh(user)
    
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="role_change",
        target_type="user",
        target_id=str(user.id),
        description=f"Changed role of user {user.email} from {old_role} to {role_update.role}"
    )
    
    return user


@router.post("/{user_id}/force-reset-password", status_code=200)
def force_reset_password(
    user_id: UUID,
    payload: ForceResetPasswordSchema,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """
    Admin-only: Force-set a new password for a user.
    The user will need to use this temporary password to log in.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Password complexity is enforced by ForceResetPasswordSchema (Pydantic).
    # No inline check needed here.

    user.password_hash = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    user.failed_login_attempts = 0
    if user.status == "suspect":
        user.status = "active"
    db.commit()

    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="force_password_reset",
        target_type="user",
        target_id=str(user.id),
        description=f"Admin force-reset password for user {user.email}",
    )

    return {"message": f"Password has been reset for {user.email}."}

