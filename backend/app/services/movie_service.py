from sqlalchemy.orm import Session
from uuid import UUID
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
