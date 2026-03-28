from sqlalchemy.orm import Session
from uuid import UUID
import os
import shutil
import uuid
from fastapi import UploadFile, HTTPException
from ..models import movie as movie_model
from ..schemas.movie import MovieCreateSchema, MovieUpdateSchema

def get_movie(db: Session, movie_id: UUID):
    """
    Fetches a single movie by its UUID.
    """
    return db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()

def get_movies(db: Session, page: int = 1, limit: int = 100):
    """
    Fetches a paginated list of movies.
    """
    skip = (page - 1) * limit
    
    total = db.query(movie_model.Movie).count()
    items = db.query(movie_model.Movie).offset(skip).limit(limit).all()
    
    return {"items": items, "total": total}

def create_movie(db: Session, movie_data: MovieCreateSchema):
    """
    Creates a new movie.
    """
    db_movie = movie_model.Movie(
        title=movie_data.title,
        overview=movie_data.overview,
        release_date=movie_data.release_date,
        genres=movie_data.genres,
        director=movie_data.director,
    )
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    return db_movie

def update_movie(db: Session, movie_id: UUID, movie_data: MovieUpdateSchema):
    """
    Updates an existing movie. Only updates DB-recognized fields.
    """
    db_movie = get_movie(db, movie_id)
    if db_movie is None:
        return None

    update_data = movie_data.model_dump(exclude_unset=True)
    # Ignore Frontend virtual URL bindings intrinsically if accidentally passed 
    if "poster_url" in update_data:
        del update_data["poster_url"]
    if "backdrop_url" in update_data:
        del update_data["backdrop_url"]

    for field, value in update_data.items():
        if hasattr(db_movie, field):
            setattr(db_movie, field, value)

    db.commit()
    db.refresh(db_movie)
    return db_movie

def delete_movie(db: Session, movie_id: UUID):
    """
    Deletes a movie by its UUID. Returns True if deleted, False if not found.
    """
    db_movie = get_movie(db, movie_id)
    if db_movie is None:
        return False

    db.delete(db_movie)
    db.commit()
    return True

def upload_image(db: Session, movie_id: UUID, file: UploadFile, image_type: str):
    """
    Validates and saves a poster or backdrop image to disk, then updates the movie record.
    """
    db_movie = get_movie(db, movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG, PNG, or WEBP allowed.")

    from datetime import datetime
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{image_type}_{timestamp}.{ext}"

    if image_type == "poster":
        folder = os.path.join("media", "images", "posters", f"movie_{movie_id}")
    else:
        folder = os.path.join("media", "images", "backdrops", f"movie_{movie_id}")

    os.makedirs(folder, exist_ok=True)
    file_path = os.path.normpath(os.path.join(folder, unique_filename)).replace("\\", "/")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if image_type == "poster":
        db_movie.poster_path = file_path
    else:
        db_movie.backdrop_path = file_path

    db.commit()
    db.refresh(db_movie)
    return db_movie

def upload_video(db: Session, movie_id: UUID, file: UploadFile):
    """
    Validates and saves an mp4 video file to disk, then updates the movie record.
    Status is strictly moved to "uploaded" preventing premature playback.
    """
    db_movie = get_movie(db, movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    allowed_types = ["video/mp4"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only MP4 allowed.")

    # Cleanup existing native files safely
    if db_movie.video_source_path:
        old_path = db_movie.video_source_path
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass
                
    if db_movie.hls_playlist_path:
        old_hls_folder = os.path.dirname(db_movie.hls_playlist_path)
        if os.path.exists(old_hls_folder):
            try:
                shutil.rmtree(old_hls_folder)
            except Exception:
                pass

    from datetime import datetime
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "mp4"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"source_{timestamp}.{ext}"

    folder = os.path.join("media", "videos", "source", f"movie_{movie_id}")
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.normpath(os.path.join(folder, unique_filename)).replace("\\", "/")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    db_movie.video_original_filename = file.filename
    db_movie.video_source_path = file_path
    db_movie.processing_status = "uploaded"
    db_movie.hls_playlist_path = None

    db.commit()
    db.refresh(db_movie)
    return db_movie
