from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from ..schemas import movie as movie_schema
from .. import database
from ..services import movie_service
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/movies",
    tags=["movies"],
)

@router.get("", response_model=movie_schema.MovieListResponseSchema)
def read_movies(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(database.get_db)
):
    """
    Retrieve a paginated list of movies.
    """
    movie_data = movie_service.get_movies(db, page=page, limit=limit)
    return {
        "items": movie_data["items"],
        "total": movie_data["total"],
        "page": page,
        "limit": limit
    }

@router.get("/{movie_id}", response_model=movie_schema.MovieDetailSchema)
def read_movie(movie_id: UUID, db: Session = Depends(database.get_db)):
    """
    Retrieve details for a specific movie by its UUID.
    """
    db_movie = movie_service.get_movie(db, movie_id=movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie

@router.post("", response_model=movie_schema.MovieDetailSchema, status_code=201)
def create_movie(
    movie: movie_schema.MovieCreateSchema,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Create a new movie.
    """
    return movie_service.create_movie(db, movie)

@router.put("/{movie_id}", response_model=movie_schema.MovieDetailSchema)
def update_movie(
    movie_id: UUID,
    movie: movie_schema.MovieUpdateSchema,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Update an existing movie.
    """
    db_movie = movie_service.update_movie(db, movie_id, movie)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie

@router.delete("/{movie_id}", status_code=204)
def delete_movie(movie_id: UUID, db: Session = Depends(database.get_db), admin_user=Depends(get_current_admin_user)):
    """
    Delete a movie.
    """
    deleted = movie_service.delete_movie(db, movie_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Movie not found")
    return None
