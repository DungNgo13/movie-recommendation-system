from pydantic import BaseModel, Field, ConfigDict, computed_field, field_validator
from typing import List, Optional, Union
from uuid import UUID
from datetime import date

# Helper to normalize local DB paths into public HTTP formats dynamically.
def normalize_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http"):
        return path
    # Removes leading slashes effectively ensuring predictable binding.
    clean_path = path.lstrip("/\\")
    return f"http://localhost:8000/{clean_path}"

# Schema for an item in the movie list
class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    
    # Exclude internal _path representations safely bridging local/prod natively
    poster_path: Optional[str] = Field(None, exclude=True)
    backdrop_path: Optional[str] = Field(None, exclude=True)
    processing_status: Optional[str] = Field("no_video", exclude=True)
    processing_progress: Optional[int] = Field(0, exclude=True)
    hls_playlist_path: Optional[str] = Field(None, exclude=True)
    
    release_date: Optional[date] = Field(None, exclude=True)
    genres: Optional[List[str]] = []

    @computed_field
    @property
    def poster_url(self) -> Optional[str]:
        return normalize_url(self.poster_path)
        
    @computed_field
    @property
    def backdrop_url(self) -> Optional[str]:
        return normalize_url(self.backdrop_path)
        
    @computed_field
    @property
    def video_status(self) -> Optional[str]:
        return self.processing_status

    @computed_field
    @property
    def video_progress(self) -> int:
        return self.processing_progress or 0
        
    @computed_field
    @property
    def hls_playlist_url(self) -> Optional[str]:
        return normalize_url(self.hls_playlist_path)

    @computed_field
    @property
    def release_year(self) -> Optional[int]:
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
    
    video_original_filename: Optional[str] = None
    processing_error: Optional[str] = None

    # Excluded Physical Native Paths
    poster_path: Optional[str] = Field(None, exclude=True)
    backdrop_path: Optional[str] = Field(None, exclude=True)
    video_source_path: Optional[str] = Field(None, exclude=True)
    processing_status: Optional[str] = Field("no_video", exclude=True)
    processing_progress: Optional[int] = Field(0, exclude=True)
    hls_playlist_path: Optional[str] = Field(None, exclude=True)

    @computed_field
    @property
    def poster_url(self) -> Optional[str]:
        return normalize_url(self.poster_path)

    @computed_field
    @property
    def backdrop_url(self) -> Optional[str]:
        return normalize_url(self.backdrop_path)
        
    @computed_field
    @property
    def video_url(self) -> Optional[str]:
        return normalize_url(self.video_source_path)

    @computed_field
    @property
    def video_status(self) -> Optional[str]:
        return self.processing_status

    @computed_field
    @property
    def video_progress(self) -> int:
        return self.processing_progress or 0
        
    @computed_field
    @property
    def hls_playlist_url(self) -> Optional[str]:
        return normalize_url(self.hls_playlist_path)

# Schema for creating a new movie (Matches Frontend Expected input!)
class MovieCreateSchema(BaseModel):
    title: str
    overview: Optional[str] = None
    release_date: Union[date, str, int, None] = None
    genres: Optional[List[str]] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    @field_validator('release_date')
    @classmethod
    def parse_release_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        # Assuming it's a 4-digit string or int
        v_str = str(v).strip()
        if len(v_str) == 4 and v_str.isdigit():
            # Pad to first of year so DB handles it properly
            return date(int(v_str), 1, 1)
        # Attempt standard parse if given full "YYYY-MM-DD"
        try:
            return date.fromisoformat(v_str)
        except ValueError:
            raise ValueError("Release date must be 'YYYY' or 'YYYY-MM-DD'")

# Schema for updating an existing movie (All fields optional)
class MovieUpdateSchema(BaseModel):
    title: Optional[str] = None
    overview: Optional[str] = None
    release_date: Union[date, str, int, None] = None
    genres: Optional[List[str]] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    @field_validator('release_date')
    @classmethod
    def parse_release_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        # Assuming it's a 4-digit string or int
        v_str = str(v).strip()
        if len(v_str) == 4 and v_str.isdigit():
            return date(int(v_str), 1, 1)
        try:
            return date.fromisoformat(v_str)
        except ValueError:
            raise ValueError("Release date must be 'YYYY' or 'YYYY-MM-DD'")

# Schema for the paginated movie list response
class MovieListResponseSchema(BaseModel):
    items: List[MovieListItemSchema]
    total: int
    page: int
    limit: int
