from sqlalchemy import Column, Integer, String, Text
from ..database import Base

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True, nullable=False)
    description = Column(Text, nullable=True)
    release_year = Column(Integer, nullable=True)
    genre = Column(String(100), index=True, nullable=True)
