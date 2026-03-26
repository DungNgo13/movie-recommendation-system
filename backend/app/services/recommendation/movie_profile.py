"""
Module to build text profiles from movie metadata for TF-IDF vectorization.

Each movie's text profile is a single string combining:
- title (weighted 2x by repetition for importance)
- overview
- genres
- director
"""


def build_movie_text(movie) -> str:
    """
    Build a single text string from a movie's metadata.
    The movie can be a SQLAlchemy model or any object with the expected attributes.
    
    Title is repeated to give it more weight in TF-IDF.
    """
    parts: list[str] = []

    title = getattr(movie, "title", "") or ""
    if title:
        # Repeat title for higher TF-IDF weight
        parts.append(title)
        parts.append(title)

    overview = getattr(movie, "overview", "") or ""
    if overview:
        parts.append(overview)

    genres = getattr(movie, "genres", None)
    if genres and isinstance(genres, list):
        parts.append(" ".join(str(g) for g in genres))

    director = getattr(movie, "director", "") or ""
    if director:
        parts.append(f"director {director}")

    return " ".join(parts).strip()


def build_movie_corpus(movies: list) -> list[str]:
    """
    Build a list of text documents from a list of movies.
    Each document corresponds to one movie's combined text profile.
    Returns texts in the same order as the input movies list.
    """
    return [build_movie_text(movie) for movie in movies]
