from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class WatchProgressPayload(BaseModel):
    """Request body for saving watch progress."""
    movie_id: str
    current_time_seconds: int = Field(ge=0)
    duration_seconds: int = Field(ge=0, default=0)
    progress_percent: float = Field(ge=0.0, le=100.0, default=0.0)


class WatchProgressResponse(BaseModel):
    """Response for a saved or fetched watch progress record."""
    movie_id: str
    current_time_seconds: int
    duration_seconds: int
    progress_percent: float
    is_completed: bool
    watched_at: Optional[datetime] = None
