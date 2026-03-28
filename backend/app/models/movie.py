import uuid
from sqlalchemy import Column, String, Text, Date
from sqlalchemy.dialects.postgresql import UUID, JSON
from ..database import Base

class Movie(Base):
    __tablename__ = "movies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), index=True, nullable=False)
    overview = Column(Text, nullable=True)
    release_date = Column(Date, nullable=True)
    genres = Column(JSON, nullable=True)
    director = Column(String(100), nullable=True)
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    video_source_path = Column(String(255), nullable=True)
    video_original_filename = Column(String(255), nullable=True)
    processing_status = Column(String(50), default="pending")
    hls_playlist_path = Column(String(255), nullable=True)
    processing_error = Column(Text, nullable=True)
