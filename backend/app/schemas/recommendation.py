from pydantic import BaseModel
from typing import Optional


class RecommendedMovieSchema(BaseModel):
    id: str
    title: str
    poster_url: Optional[str] = None
    release_year: Optional[int] = None
    score: float
    reason: str
