from sqlalchemy.orm import Session
from .. import models, schemas

def get_movie(db: Session, movie_id: int):
    return db.query(models.movie.Movie).filter(models.movie.Movie.id == movie_id).first()

def get_movies(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.movie.Movie).offset(skip).limit(limit).all()

def create_movie(db: Session, movie: schemas.movie.MovieCreate):
    db_movie = models.movie.Movie(**movie.dict())
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    return db_movie
