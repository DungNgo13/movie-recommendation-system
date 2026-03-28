from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from uuid import UUID

from ..schemas import movie as movie_schema
from .. import database
from ..services import movie_service
from .auth import get_current_admin_user
from ..services.admin_service import create_audit_log

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
    new_movie = movie_service.create_movie(db, movie)
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_create",
        target_type="movie",
        target_id=str(new_movie.id),
        description=f"Created movie '{new_movie.title}'"
    )
    return new_movie

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
        
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Updated movie '{db_movie.title}'"
    )
    return db_movie

@router.delete("/{movie_id}", status_code=204)
def delete_movie(movie_id: UUID, db: Session = Depends(database.get_db), admin_user=Depends(get_current_admin_user)):
    """
    Delete a movie.
    """
    movie_to_delete = movie_service.get_movie(db, movie_id)
    if not movie_to_delete:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    title = movie_to_delete.title
    deleted = movie_service.delete_movie(db, movie_id)
    
    if deleted:
        create_audit_log(
            db=db,
            admin_email=admin_user.email,
            action_type="movie_delete",
            target_type="movie",
            target_id=str(movie_id),
            description=f"Deleted movie '{title}'"
        )
    return None

@router.post("/{movie_id}/poster", response_model=movie_schema.MovieDetailSchema)
def upload_poster(
    movie_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Upload a new poster image for a movie.
    """
    db_movie = movie_service.upload_image(db, movie_id, file, "poster")
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Uploaded poster for movie '{db_movie.title}'"
    )
    return db_movie

@router.post("/{movie_id}/backdrop", response_model=movie_schema.MovieDetailSchema)
def upload_backdrop(
    movie_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Upload a new backdrop image for a movie.
    """
    db_movie = movie_service.upload_image(db, movie_id, file, "backdrop")
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Uploaded backdrop for movie '{db_movie.title}'"
    )
    return db_movie
