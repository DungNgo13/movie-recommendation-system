from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from .. import database
from ..schemas.admin import AdminAuditLogSchema
from ..services.admin_service import get_audit_logs
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/logs",
    tags=["admin_logs"],
)

@router.get("", response_model=List[AdminAuditLogSchema])
def get_all_audit_logs(
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Get a list of all recent admin audit logs.
    """
    return get_audit_logs(db, limit=100)
