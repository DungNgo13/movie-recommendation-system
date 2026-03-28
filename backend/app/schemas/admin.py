from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class AdminDashboardSchema(BaseModel):
    total_movies: int
    total_users: int
    total_admins: int
    total_favorites: int
    total_ratings: int
    total_watch_history: int

class AdminAuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_user_email: str
    action_type: str
    target_type: str
    target_id: str | None
    description: str | None
    created_at: datetime
