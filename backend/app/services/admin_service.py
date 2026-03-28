from sqlalchemy.orm import Session
from ..models.admin_audit_log import AdminAuditLog
from ..models.user import User

def create_audit_log(
    db: Session,
    admin_email: str,
    action_type: str,
    target_type: str,
    target_id: str | None,
    description: str | None
):
    log = AdminAuditLog(
        admin_user_email=admin_email,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        description=description
    )
    db.add(log)
    db.commit()

def get_audit_logs(db: Session, limit: int = 100):
    return db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit).all()

def check_is_last_admin(db: Session, user: User) -> bool:
    """Returns True if this user is the last remaining admin."""
    if user.role != "admin":
        return False
    # Count how many admins exist
    admin_count = db.query(User).filter(User.role == "admin").count()
    return admin_count <= 1
