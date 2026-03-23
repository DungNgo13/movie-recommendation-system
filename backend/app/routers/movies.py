from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import schemas, database
from ..services import movie_service

router = APIRouter(
    prefix="/movies",
    tags=["movies"],
)

@router.post("/", response_model=schemas.movie.Movie)
def create_movie(movie: schemas.movie.MovieCreate, db: Session = Depends(database.get_db)):
    return movie_service.create_movie(db=db, movie=movie)

@router.get("/", response_model=List[schemas.movie.Movie])
def read_movies(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    movies = movie_service.get_movies(db, skip=skip, limit=limit)
    return movies

@router.get("/{movie_id}", response_model=schemas.movie.Movie)
def read_movie(movie_id: int, db: Session = Depends(database.get_db)):
    db_movie = movie_service.get_movie(db, movie_id=movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie
