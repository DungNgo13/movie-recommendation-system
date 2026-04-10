import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class WatchHistory(Base):
    __tablename__ = "watch_history"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie_watch"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id"), nullable=False)
    watched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    progress_percent = Column(Integer, default=0)
    playback_position_seconds = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0, nullable=True)
    is_completed = Column(Boolean, default=False, nullable=False)

