"""
Wikimedia Commons media importer.

Imports image/video assets ONLY if the file license is verified as:
  - Public Domain
  - CC0
  - CC BY (any version)
  - CC BY-SA (any version)

Rejects CC BY-NC, CC BY-ND, All Rights Reserved, and unknown licenses.

Expected input JSON format:
[
  {
    "movie_id": "uuid-string",
    "asset_type": "poster",
    "url": "https://upload.wikimedia.org/...",
    "source_url": "https://commons.wikimedia.org/wiki/File:...",
    "license_type": "CC BY-SA 4.0",
    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "attribution": "Photo by ..., CC BY-SA 4.0"
  }
]

Usage:
    python -m scripts.importers.import_wikimedia_commons --input wikimedia_assets.json
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
from app.services.license_checker import allow_license, normalize_license, get_media_rights_status

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def import_wikimedia(input_path: str) -> None:
    db = SessionLocal()
    try:
        with open(input_path, encoding="utf-8") as f:
            records = json.load(f)

        imported = 0
        rejected = 0

        for rec in records:
            raw_license = rec.get("license_type", "")
            canonical = normalize_license(raw_license)

            if not allow_license(raw_license):
                logger.warning(
                    "REJECTED: unsupported license '%s' (canonical: '%s') for %s",
                    raw_license, canonical, rec.get("url", "?"),
                )
                rejected += 1
                continue

            asset = MovieAsset(
                movie_id=UUID(rec["movie_id"]),
                asset_type=rec.get("asset_type", "poster"),
                url=rec.get("url"),
                source_name="Wikimedia Commons",
                source_url=rec.get("source_url"),
                license_type=canonical,
                license_url=rec.get("license_url"),
                attribution=rec.get("attribution"),
                is_public_domain=canonical in {"Public Domain", "CC0 1.0"},
                media_rights_status=get_media_rights_status(raw_license),
            )
            db.add(asset)
            imported += 1

        db.commit()
        logger.info("Imported %d assets, rejected %d", imported, rejected)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Import Wikimedia Commons media")
    parser.add_argument("--input", required=True, help="Path to JSON asset list")
    args = parser.parse_args()
    import_wikimedia(args.input)


if __name__ == "__main__":
    main()
