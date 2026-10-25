"""
Validate the R2 upload-session migrations (f7c3d9a1b2e4 + a1e5c7b9d3f2)
against a DISPOSABLE PostgreSQL database.

    python scripts/validate_migration_pg.py \
        --url postgresql://user:pass@localhost:55432/movsug_migration_check \
        --confirm-disposable

Safety guards (the script refuses to run unless ALL hold):
  * ``--confirm-disposable`` is passed;
  * the URL uses the PostgreSQL dialect;
  * the URL differs from DATABASE_URL in the environment / backend/.env;
  * the target database contains NO tables (fresh, empty database).

What it does:
  1. Checks Alembic revision continuity (single head, unbroken chain).
  2. Builds the pre-migration schema (revision e5f3a1b2c7d8) from the models,
     because the repository's baseline migration only ALTERs pre-existing
     tables and cannot bootstrap an empty database.
  3. Seeds one movie, then runs upgrade → downgrade → upgrade, verifying data
     preservation, the ``source_storage`` default, foreign keys (ON DELETE),
     the unique constraint and indexes after each step.

The URL (and its password) is never printed.
"""

import argparse
import os
import sys
import uuid

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

PREVIOUS_REVISION = "e5f3a1b2c7d8"      # last revision before R2 work
R2_REVISION = "f7c3d9a1b2e4"            # movies columns + upload_sessions
TARGET_REVISION = "a1e5c7b9d3f2"        # cleanup tracking (current head)
NEW_COLUMNS = ("source_storage", "source_object_key")


class GuardError(RuntimeError):
    pass


def _configured_database_url() -> str:
    from dotenv import dotenv_values

    file_values = dotenv_values(os.path.join(BACKEND_DIR, ".env"))
    return os.environ.get("DATABASE_URL") or file_values.get("DATABASE_URL") or ""


def check_guards(url: str, confirm: bool) -> None:
    from sqlalchemy.engine import make_url

    if not confirm:
        raise GuardError("Refusing: pass --confirm-disposable for a throwaway database.")
    if make_url(url).get_backend_name() != "postgresql":
        raise GuardError("Refusing: --url must be a PostgreSQL URL.")
    configured = _configured_database_url()
    if configured and make_url(configured) == make_url(url):
        raise GuardError("Refusing: --url equals the configured DATABASE_URL.")


def check_revision_chain(config) -> list:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if heads != [TARGET_REVISION]:
        raise AssertionError(f"expected single head {TARGET_REVISION}, got {heads}")
    chain = [rev.revision for rev in script.walk_revisions("base", "heads")]
    if chain[:3] != [TARGET_REVISION, R2_REVISION, PREVIOUS_REVISION]:
        raise AssertionError(f"unexpected revision order near head: {chain[:3]}")
    return chain


class Checker:
    def __init__(self):
        self.failures = 0

    def check(self, label: str, ok: bool) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            self.failures += 1


def _verify_upgraded(engine, movie_id, checker: Checker, step: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
        row = conn.execute(text("select title, source_storage, source_object_key "
                                "from movies where id = :id"), {"id": movie_id}).one()
    checker.check(f"{step}: alembic version is {TARGET_REVISION}", version == TARGET_REVISION)
    checker.check(f"{step}: seeded movie preserved", row.title == "Migration Seed")
    checker.check(f"{step}: source_storage defaults to 'local'", row.source_storage == "local")
    checker.check(f"{step}: source_object_key is NULL", row.source_object_key is None)

    fks = {fk["referred_table"]: fk.get("options", {}).get("ondelete")
           for fk in insp.get_foreign_keys("upload_sessions")}
    checker.check(f"{step}: FK movie_id -> movies ON DELETE CASCADE",
                  (fks.get("movies") or "").upper() == "CASCADE")
    checker.check(f"{step}: FK created_by_user_id -> users ON DELETE SET NULL",
                  (fks.get("users") or "").upper() == "SET NULL")
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("upload_sessions")}
    checker.check(f"{step}: UNIQUE(object_key)", ("object_key",) in uniques)
    indexes = {i["name"] for i in insp.get_indexes("upload_sessions")}
    checker.check(f"{step}: index ix_upload_sessions_movie_status",
                  "ix_upload_sessions_movie_status" in indexes)
    checker.check(f"{step}: index ix_upload_sessions_status_expires",
                  "ix_upload_sessions_status_expires" in indexes)
    cols = {c["name"] for c in insp.get_columns("upload_sessions")}
    checker.check(f"{step}: column upload_sessions.object_deleted_at",
                  "object_deleted_at" in cols)


def _verify_downgraded(engine, movie_id, checker: Checker) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("movies")}
    with engine.connect() as conn:
        version = conn.execute(text("select version_num from alembic_version")).scalar()
        title = conn.execute(text("select title from movies where id = :id"),
                             {"id": movie_id}).scalar()
    checker.check(f"downgrade: alembic version is {PREVIOUS_REVISION}", version == PREVIOUS_REVISION)
    checker.check("downgrade: upload_sessions dropped", "upload_sessions" not in insp.get_table_names())
    checker.check("downgrade: movie source columns dropped", not (set(NEW_COLUMNS) & cols))
    checker.check("downgrade: seeded movie preserved", title == "Migration Seed")


def run(url: str) -> int:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text

    os.environ["DATABASE_URL"] = url  # alembic/env.py reads DATABASE_URL
    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))

    checker = Checker()
    chain = check_revision_chain(config)
    checker.check(f"revision chain continuous ({len(chain)} revisions, single head)", True)

    engine = create_engine(url)
    if inspect(engine).get_table_names():
        raise GuardError("Refusing: target database is not empty.")

    from app.database import Base
    from app.models import (admin_audit_log, movie, movie_asset, rating,  # noqa: F401
                            upload_session, user, user_favorite, watch_history)

    pre_tables = [t for name, t in Base.metadata.tables.items() if name != "upload_sessions"]
    Base.metadata.create_all(bind=engine, tables=pre_tables)
    movie_id = uuid.uuid4()
    with engine.begin() as conn:
        for column in NEW_COLUMNS:
            conn.execute(text(f"ALTER TABLE movies DROP COLUMN {column}"))
        conn.execute(text("insert into movies (id, title, is_public_domain, media_rights_status) "
                          "values (:id, 'Migration Seed', false, 'unknown')"), {"id": movie_id})
    command.stamp(config, PREVIOUS_REVISION)

    command.upgrade(config, "head")
    _verify_upgraded(engine, movie_id, checker, "upgrade#1")
    command.downgrade(config, PREVIOUS_REVISION)
    _verify_downgraded(engine, movie_id, checker)
    command.upgrade(config, "head")
    _verify_upgraded(engine, movie_id, checker, "upgrade#2")
    engine.dispose()

    print(f"RESULT: {'PASS' if checker.failures == 0 else 'FAIL'} "
          f"({checker.failures} failed checks)")
    return 0 if checker.failures == 0 else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate R2 migration on disposable PostgreSQL.")
    parser.add_argument("--url", required=True, help="Disposable PostgreSQL URL (never printed).")
    parser.add_argument("--confirm-disposable", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_guards(args.url, args.confirm_disposable)
        return run(args.url)
    except GuardError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
