from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class RatingCreateSchema(BaseModel):
    movie_id: UUID
    rating: int = Field(ge=1, le=5)


class RatingResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    movie_id: UUID
    rating: int
    created_at: datetime
    updated_at: datetime


class MovieRatingSchema(BaseModel):
    """Rating info for a specific movie by the current user."""
    movie_id: str
    rating: Optional[int] = None
