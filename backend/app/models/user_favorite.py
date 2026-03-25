import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class UserFavorite(Base):
    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_user_movie"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
