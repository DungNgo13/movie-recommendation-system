from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class HistoryItemSchema(BaseModel):
    """Movie data returned in watch history list."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    poster_url: Optional[str] = None
    release_year: Optional[int] = None
    watched_at: datetime
