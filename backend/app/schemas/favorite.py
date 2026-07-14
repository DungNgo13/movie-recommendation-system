from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class FavoriteMovieSchema(BaseModel):
    """Movie data returned in favorites list."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    poster_url: Optional[str] = None
    release_year: Optional[int] = None


class FavoriteResponseSchema(BaseModel):
    """Response for a single favorite action."""
    movie_id: str
    favorited: bool


class GuestFavoriteMergeSchema(BaseModel):
    """Payload for merging guest favorite movie IDs after login."""
    movie_ids: list[str] = Field(default_factory=list, max_length=100)

