"""
Module to build text profiles from movie metadata for TF-IDF vectorization.

Each movie's text profile is a single string combining:
- title     (weighted ×2 by repetition)
- overview
- genres
- cast      (actor names, each prefixed with "actor" so TF-IDF treats the
             token as domain-specific rather than a plain name)
- keywords  (weighted ×2 by repetition — concise thematic tags deserve
             higher weight than long freeform text)
- director  (prefixed with "director" for the same disambiguation reason)
"""


def build_movie_text(movie) -> str:
    """
    Build a single text string from a movie's metadata.
    The movie can be a SQLAlchemy model or any object with the expected attributes.

    Field weights (achieved through repetition in the corpus string):
      - title    ×2  — primary identity token
      - keywords ×2  — concise thematic signal; high signal-to-noise ratio
      - overview ×1  — rich context but may contain irrelevant words
      - genres   ×1  — categorical signal
      - cast     ×1  — one token per actor ("actor <name>")
      - director ×1  — one token ("director <name>")
    """
    parts: list[str] = []

    # ── Title (×2 repetition for higher TF-IDF weight) ───────────────────────
    title = getattr(movie, "title", "") or ""
    if title:
        parts.append(title)
        parts.append(title)

    # ── Overview ──────────────────────────────────────────────────────────────
    overview = getattr(movie, "overview", "") or ""
    if overview:
        parts.append(overview)

    # ── Genres ────────────────────────────────────────────────────────────────
    genres = getattr(movie, "genres", None)
    if genres and isinstance(genres, list):
        parts.append(" ".join(str(g) for g in genres))

    # ── Cast: prefix each actor name with "actor" so the vocabulary token is
    #    distinctive (e.g. "actor tom hanks" vs. the plain word "hanks"). ──────
    cast = getattr(movie, "cast", None)
    if cast and isinstance(cast, list):
        parts.append(" ".join(f"actor {str(a).lower()}" for a in cast))

    # ── Keywords (×2 repetition — concise tags deserve extra weight) ──────────
    keywords = getattr(movie, "keywords", None)
    if keywords and isinstance(keywords, list):
        kw_str = " ".join(str(k).lower() for k in keywords)
        parts.append(kw_str)
        parts.append(kw_str)

    # ── Director ──────────────────────────────────────────────────────────────
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
