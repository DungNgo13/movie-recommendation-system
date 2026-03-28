from pydantic import BaseModel, Field, ConfigDict, computed_field
from typing import List, Optional
from uuid import UUID
from datetime import date

# Schema for an item in the movie list
class MovieListItemSchema(BaseModel):
    # Use ConfigDict for Pydantic V2 and from_attributes instead of orm_mode
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    poster_url: Optional[str] = None
    video_status: Optional[str] = "pending"
    # This field is used for computation but excluded from the final response
    release_date: Optional[date] = Field(None, exclude=True)

    @computed_field
    @property
    def release_year(self) -> Optional[int]:
        """Computes release_year from release_date."""
        if self.release_date:
            return self.release_date.year
        return None

# Schema for the detailed movie view
class MovieDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    overview: Optional[str] = None
    release_date: Optional[date] = None
    genres: Optional[List[str]] = []
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    video_url: Optional[str] = None
    video_status: Optional[str] = "pending"

# Schema for creating a new movie
class MovieCreateSchema(BaseModel):
    title: str
    overview: Optional[str] = None
    release_date: Optional[date] = None
    genres: Optional[List[str]] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

# Schema for updating an existing movie (all fields optional)
class MovieUpdateSchema(BaseModel):
    title: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[date] = None
    genres: Optional[List[str]] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

# Schema for the paginated movie list response
class MovieListResponseSchema(BaseModel):
    items: List[MovieListItemSchema]
    total: int
    page: int
    limit: int
