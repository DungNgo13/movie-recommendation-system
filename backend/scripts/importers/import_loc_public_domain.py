"""
Library of Congress public-domain importer.

Imports public-domain films and associated assets from seed JSON or
LOC API-ready data. All assets are marked as safe_to_use and
is_public_domain=True.

Reads from the existing public_domain_movies.json seed file or a
compatible JSON array.

Usage:
    python -m scripts.importers.import_loc_public_domain \
        --input scripts/public_domain_movies.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import SessionLocal
from app.models.movie import Movie
from app.models.movie_asset import MovieAsset

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def import_loc(input_path: str) -> None:
    db = SessionLocal()
    try:
        with open(input_path, encoding="utf-8") as f:
            records = json.load(f)

        movies_created = 0
        assets_created = 0

        for rec in records:
            # Parse release_date
            rd_raw = rec.get("release_date")
            release_date = None
            if rd_raw:
                try:
                    release_date = date.fromisoformat(rd_raw)
                except ValueError:
                    pass

            movie = Movie(
                title=rec["title"],
                overview=rec.get("overview"),
                release_date=release_date,
                genres=rec.get("genres"),
                cast=rec.get("cast"),
                keywords=rec.get("keywords"),
                director=rec.get("director"),
                source_name=rec.get("source_name", "Library of Congress"),
                source_url=rec.get("source_url"),
                license_type=rec.get("license_type", "Public Domain"),
                license_url=rec.get("license_url"),
                attribution=rec.get("attribution"),
                is_public_domain=True,
                media_rights_status="safe_to_use",
            )
            db.add(movie)
            db.flush()  # get movie.id for asset FK
            movies_created += 1

            # If the record includes asset URLs, create MovieAsset records
            for asset_field, asset_type in [
                ("poster_url", "poster"),
                ("backdrop_url", "backdrop"),
                ("video_url", "full_video"),
            ]:
                url = rec.get(asset_field)
                if url:
                    asset = MovieAsset(
                        movie_id=movie.id,
                        asset_type=asset_type,
                        url=url,
                        source_name=rec.get("source_name", "Library of Congress"),
                        source_url=rec.get("source_url"),
                        license_type="Public Domain",
                        is_public_domain=True,
                        media_rights_status="safe_to_use",
                        attribution=rec.get("attribution"),
                    )
                    db.add(asset)
                    assets_created += 1

        db.commit()
        logger.info(
            "Imported %d movies and %d assets from LOC",
            movies_created, assets_created,
        )
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import LOC public-domain films")
    parser.add_argument("--input", required=True, help="Path to JSON seed file")
    args = parser.parse_args()
    import_loc(args.input)


if __name__ == "__main__":
    main()
