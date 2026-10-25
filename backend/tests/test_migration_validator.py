"""
Offline tests for scripts/validate_migration_pg.py: safety guards and Alembic
revision continuity.  No database connection is made.
"""

import importlib.util
import os

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PG_URL = "postgresql://tester:pw-should-not-print@localhost:1/disposable_check"


def _load():
    path = os.path.join(BACKEND_DIR, "scripts", "validate_migration_pg.py")
    spec = importlib.util.spec_from_file_location("validate_migration_pg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validator(monkeypatch):
    module = _load()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./unrelated.db")
    return module


def test_requires_confirmation(validator):
    with pytest.raises(validator.GuardError, match="confirm-disposable"):
        validator.check_guards(PG_URL, confirm=False)


def test_rejects_non_postgres_urls(validator):
    with pytest.raises(validator.GuardError, match="PostgreSQL"):
        validator.check_guards("sqlite:///./x.db", confirm=True)


def test_rejects_configured_database_url(validator, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    with pytest.raises(validator.GuardError, match="configured DATABASE_URL"):
        validator.check_guards(PG_URL, confirm=True)


def test_accepts_distinct_disposable_postgres_url(validator):
    validator.check_guards(PG_URL, confirm=True)


def test_main_refusal_exit_code_and_no_password_leak(validator, capsys):
    assert validator.main(["--url", PG_URL]) == 2
    assert "pw-should-not-print" not in capsys.readouterr().out


def test_revision_chain_single_head_and_continuous(validator):
    from alembic.config import Config

    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    chain = validator.check_revision_chain(config)
    assert chain[0] == validator.TARGET_REVISION == "a1e5c7b9d3f2"
    assert chain[1] == validator.R2_REVISION == "f7c3d9a1b2e4"
    assert chain[2] == validator.PREVIOUS_REVISION
    assert chain[-1] == "1780d0eefc59"
    assert len(chain) == len(set(chain))
