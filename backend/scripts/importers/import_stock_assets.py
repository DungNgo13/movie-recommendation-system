"""
Stock asset importer (Pexels / Pixabay / Unsplash).

Imports stock images as backdrop, banner, or placeholder assets ONLY.
Never marks stock images as 'poster' — they are not official movie posters.

Expected input JSON format:
[
  {
    "movie_id": "uuid-string",
    "asset_type": "backdrop",
    "url": "https://images.pexels.com/photos/...",
    "source_name": "Pexels",
    "source_url": "https://www.pexels.com/photo/...",
    "license_type": "Pexels License",
    "attribution": "Photo by ... on Pexels"
  }
]

Usage:
    python -m scripts.importers.import_stock_assets --input stock_assets.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import SessionLocal
from app.models.movie_asset import MovieAsset

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Stock images may only be used for these asset types
_ALLOWED_STOCK_TYPES = {"backdrop", "banner", "placeholder"}


def import_stock(input_path: str) -> None:
    db = SessionLocal()
    try:
        with open(input_path, encoding="utf-8") as f:
            records = json.load(f)

        imported = 0
        rejected = 0

        for rec in records:
            asset_type = rec.get("asset_type", "backdrop")

            if asset_type not in _ALLOWED_STOCK_TYPES:
                logger.warning(
                    "REJECTED: stock images cannot be used as '%s' — only %s allowed. URL: %s",
                    asset_type, _ALLOWED_STOCK_TYPES, rec.get("url", "?"),
                )
                rejected += 1
                continue

            asset = MovieAsset(
                movie_id=UUID(rec["movie_id"]),
                asset_type=asset_type,
                url=rec.get("url"),
                source_name=rec.get("source_name", "Stock Image"),
                source_url=rec.get("source_url"),
                license_type=rec.get("license_type", "Free License"),
                license_url=rec.get("license_url"),
                attribution=rec.get("attribution"),
                is_public_domain=False,
                media_rights_status="safe_to_use",
            )
            db.add(asset)
            imported += 1

        db.commit()
        logger.info("Imported %d stock assets, rejected %d", imported, rejected)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import stock image assets")
    parser.add_argument("--input", required=True, help="Path to JSON asset list")
    args = parser.parse_args()
    import_stock(args.input)


if __name__ == "__main__":
    main()
