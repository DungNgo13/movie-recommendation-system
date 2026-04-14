import uuid
from sqlalchemy import Column, String, Text, Date, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from ..database import Base

class Movie(Base):
    __tablename__ = "movies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), index=True, nullable=False)
    overview = Column(Text, nullable=True)
    release_date = Column(Date, nullable=True)
    genres = Column(JSON, nullable=True)       # list of genre strings, e.g. ["Action", "Drama"]
    cast = Column(JSON, nullable=True)         # list of actor names (top-billed), e.g. ["Tom Hanks"]
    keywords = Column(JSON, nullable=True)     # list of thematic tags,  e.g. ["heist", "based on true story"]
    director = Column(String(100), nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    video_source_path = Column(String(255), nullable=True)
    video_original_filename = Column(String(255), nullable=True)
    processing_status = Column(String(50), default="no_video")
    processing_progress = Column(Integer, default=0, nullable=True)
    processing_step = Column(String(100), nullable=True)
    hls_playlist_path = Column(String(255), nullable=True)
    processing_error = Column(Text, nullable=True)
    # Comma-separated list of successfully encoded quality labels, e.g. "360p,720p,1080p"
    available_qualities = Column(String(100), nullable=True)

