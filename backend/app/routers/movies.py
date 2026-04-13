from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from ..schemas import movie as movie_schema
from .. import database
from ..services import movie_service, movie_asset_service
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
    db_movie = movie_asset_service.upload_image_asset(db, movie_id, file, "poster")
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
    db_movie = movie_asset_service.upload_image_asset(db, movie_id, file, "backdrop")
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Uploaded backdrop for movie '{db_movie.title}'"
    )
    return db_movie

@router.post("/{movie_id}/video", response_model=movie_schema.MovieDetailSchema)
def upload_video(
    movie_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Upload a new mp4 source video for a movie.
    Does NOT auto-trigger HLS conversion anymore; correctly stages movie for manual triggering.
    """
    db_movie = movie_asset_service.upload_video_asset(db, movie_id, file)

    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Uploaded source video & triggered HLS processing for '{db_movie.title}'"
    )
    return db_movie

from ..services.hls_service import process_hls_conversion, cancel_encode_task

@router.post("/{movie_id}/process-hls", status_code=202)
def process_video_hls(
    movie_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Trigger async FFmpeg conversion of an uploaded source video into HLS.
    """
    db_movie = movie_service.get_movie(db, movie_id)
    if not db_movie:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    if db_movie.processing_status not in ("uploaded", "failed", "ready"):
        raise HTTPException(
            status_code=400,
            detail="Video must be in 'uploaded', 'failed', or 'ready' state to re-encode."
        )

    # Mark status immediately so the UI shows live feedback
    db_movie.processing_status = "processing"
    db_movie.processing_error = None
    db_movie.available_qualities = "Processing..."   # cleared when FFmpeg finishes
    db.commit()

    background_tasks.add_task(process_hls_conversion, movie_id)
    
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Triggered HLS conversion for movie '{db_movie.title}'"
    )
    
    return {"message": "HLS conversion started in the background."}

@router.get("/{movie_id}/status")
def get_video_status(
    movie_id: UUID, 
    db: Session = Depends(database.get_db)
):
    """
    Check the current processing status of a movie's video.
    """
    db_movie = movie_service.get_movie(db, movie_id)
    if not db_movie:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    from ..schemas.movie import normalize_url
    return {
        "video_status": db_movie.processing_status,
        "video_progress": db_movie.processing_progress or 0,
        "video_step": db_movie.processing_step,
        "processing_error": db_movie.processing_error,
        "hls_playlist_url": normalize_url(db_movie.hls_playlist_path),
        "available_qualities": db_movie.available_qualities,
    }


@router.post("/{movie_id}/cancel-encode", status_code=200)
def cancel_encode(
    movie_id: UUID,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user)
):
    """
    Kill an ongoing FFmpeg HLS encode for the given movie.

    Returns HTTP 200 when the process was killed, HTTP 409 when no encode
    is currently running for this movie.
    """
    db_movie = movie_service.get_movie(db, movie_id)
    if not db_movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    result = cancel_encode_task(movie_id)

    if not result["cancelled"]:
        raise HTTPException(status_code=409, detail=result["detail"])

    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Cancelled HLS encode for movie '{db_movie.title}'"
    )
    return result
