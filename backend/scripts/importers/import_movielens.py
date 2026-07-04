"""
MovieLens importer.

Imports movie titles, genres, ratings, and tags from MovieLens CSV files.
Does NOT import any media assets — MovieLens provides recommendation/rating
data only.

Usage:
    python -m scripts.importers.import_movielens \
        --movies path/to/movies.csv \
        --ratings path/to/ratings.csv \
        --tags path/to/tags.csv

All imported movies are marked:
    source_name = "MovieLens"
    media_rights_status = "non_commercial_only"
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import SessionLocal
from app.models.movie import Movie

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def import_movies(movies_csv: str, db) -> dict[str, Movie]:
    """Import movies.csv → Movie records. Returns {movieId: Movie}."""
    lookup: dict[str, Movie] = {}
    created = 0

    with open(movies_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ml_id = row["movieId"]
            title = row["title"].strip()
            raw_genres = row.get("genres", "")
            genres = [g.strip() for g in raw_genres.split("|") if g.strip() and g != "(no genres listed)"]

            movie = Movie(
                title=title,
                genres=genres or None,
                source_name="MovieLens",
                source_url=f"https://movielens.org/movies/{ml_id}",
                license_type="Research Use",
                media_rights_status="non_commercial_only",
            )
            db.add(movie)
            lookup[ml_id] = movie
            created += 1

    db.commit()
    logger.info("Created %d movies from MovieLens", created)
    # NOTE: No MovieAsset records created — MovieLens provides no media.
    return lookup


def import_ratings(ratings_csv: str, db, lookup: dict[str, Movie]) -> None:
    """Log rating counts — actual user-rating import is a separate concern."""
    count = 0
    with open(ratings_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for _ in reader:
            count += 1
    logger.info("Found %d ratings in CSV (import to ratings table is a separate step)", count)


def import_tags(tags_csv: str, db, lookup: dict[str, Movie]) -> None:
    """Merge tags into movie keywords."""
    tag_count = 0
    with open(tags_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ml_id = row["movieId"]
            tag = row.get("tag", "").strip().lower()
            if ml_id in lookup and tag:
                movie = lookup[ml_id]
                existing = movie.keywords or []
                if tag not in existing:
                    existing.append(tag)
                    movie.keywords = existing
                    tag_count += 1

    db.commit()
    logger.info("Added %d tags as keywords", tag_count)


def main():
    parser = argparse.ArgumentParser(description="Import MovieLens data")
    parser.add_argument("--movies", required=True, help="Path to movies.csv")
    parser.add_argument("--ratings", default=None, help="Path to ratings.csv")
    parser.add_argument("--tags", default=None, help="Path to tags.csv")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        lookup = import_movies(args.movies, db)
        if args.ratings:
            import_ratings(args.ratings, db, lookup)
        if args.tags:
            import_tags(args.tags, db, lookup)
    finally:
        db.close()


if __name__ == "__main__":
    main()
