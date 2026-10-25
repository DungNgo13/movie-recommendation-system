"""
Opt-in cleanup of abandoned / invalid direct-to-R2 uploads.

DRY-RUN by default — nothing is changed unless ``--execute`` is passed.

Usage (from the backend/ directory):

    python scripts/cleanup_r2_uploads.py                 # dry-run report
    python scripts/cleanup_r2_uploads.py --execute       # delete eligible objects
    python scripts/cleanup_r2_uploads.py --grace-hours 48 --limit 50

Safety: only failed/expired sessions (and pending sessions expired longer than
the grace period) are considered; completed sessions, objects referenced by a
movie, and keys outside a session's own namespace are never deleted.  See
app/services/upload_cleanup_service.py.

Secrets are never printed: output contains session/movie ids and actions only.
"""

import argparse
import os
import sys
from datetime import timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from app.database import SessionLocal  # noqa: E402
from app.models import movie, user, upload_session  # noqa: E402,F401  (register tables)
from app.services.r2_storage_service import (  # noqa: E402
    R2NotConfiguredError,
    load_r2_storage_from_env,
)
from app.services.upload_cleanup_service import (  # noqa: E402
    ACTION_DELETED,
    ACTION_ERROR,
    ACTION_WOULD_DELETE,
    cleanup_abandoned_uploads,
)

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_NOT_CONFIGURED = 2


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete eligible objects (default: dry-run).")
    parser.add_argument("--grace-hours", type=float, default=24.0,
                        help="Extra time after URL expiry before a pending session "
                             "is treated as abandoned (default: 24).")
    parser.add_argument("--limit", type=int, default=100,
                        help="Maximum sessions to process per run (default: 100).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    dry_run = not args.execute

    try:
        storage = load_r2_storage_from_env()
    except R2NotConfiguredError as exc:
        if not dry_run:
            print(f"ERROR: {exc}. Refusing to run with --execute.")
            return EXIT_NOT_CONFIGURED
        storage = None  # dry-run only needs the database

    db = SessionLocal()
    try:
        report = cleanup_abandoned_uploads(
            db, storage, dry_run=dry_run,
            grace=timedelta(hours=args.grace_hours), limit=args.limit,
        )
    finally:
        db.close()

    mode = "DRY-RUN" if dry_run else "EXECUTE"
    print(f"[{mode}] candidates: {len(report.items)}")
    for item in report.items:
        suffix = f" ({item.detail})" if item.detail else ""
        print(f"  session={item.session_id} movie={item.movie_id} "
              f"{item.status_before}->{item.status_after} action={item.action}{suffix}")
    print(f"[{mode}] would_delete={report.count(ACTION_WOULD_DELETE)} "
          f"deleted={report.count(ACTION_DELETED)} errors={report.count(ACTION_ERROR)}")
    return EXIT_ERRORS if report.has_errors else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
