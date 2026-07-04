"""
Wikidata metadata importer.

Imports structured movie metadata from a Wikidata SPARQL export (JSON).
Does NOT import images unless verified through Wikimedia Commons (use
import_wikimedia_commons.py for that).

Expected input JSON format (list of objects):
[
  {
    "qid": "Q47703",
    "title": "Nosferatu",
    "original_title": "Nosferatu, eine Symphonie des Grauens",
    "year": 1922,
    "country": "Germany",
    "language": "Silent",
    "director": "F.W. Murnau",
    "cast": ["Max Schreck", "Gustav von Wangenheim"],
    "runtime_minutes": 94
  }
]

Usage:
    python -m scripts.importers.import_wikidata --input wikidata_movies.json
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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def import_wikidata(input_path: str) -> None:
    db = SessionLocal()
    try:
        with open(input_path, encoding="utf-8") as f:
            records = json.load(f)

        created = 0
        for rec in records:
            qid = rec.get("qid", "")
            title = rec.get("title") or rec.get("original_title")
            if not title:
                logger.warning("Skipping record with no title: %s", qid)
                continue

            year = rec.get("year")
            release_date = date(year, 1, 1) if year else None

            movie = Movie(
                title=title,
                overview=rec.get("overview"),
                release_date=release_date,
                director=rec.get("director"),
                cast=rec.get("cast"),
                genres=rec.get("genres"),
                keywords=[f"wikidata:{qid}"] if qid else None,
                source_name="Wikidata",
                source_url=f"https://www.wikidata.org/wiki/{qid}" if qid else None,
                license_type="CC0 1.0",
                license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                media_rights_status="safe_to_use",
            )
            db.add(movie)
            created += 1
            # NOTE: No MovieAsset records — Wikidata is metadata only.

        db.commit()
        logger.info("Imported %d movies from Wikidata", created)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import Wikidata movie metadata")
    parser.add_argument("--input", required=True, help="Path to JSON export")
    args = parser.parse_args()
    import_wikidata(args.input)


if __name__ == "__main__":
    main()
