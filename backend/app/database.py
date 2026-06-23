from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# Database URL — configurable via environment variable.
# Defaults to SQLite for local development.
# For production, set DATABASE_URL in .env (e.g. "postgresql://user:pass@host/db").
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# SQLite requires check_same_thread=False; PostgreSQL does not need it.
_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# PostgreSQL benefits from connection pooling; SQLite does not.
pool_kwargs = {} if _is_sqlite else {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_pre_ping": True,  # detect stale connections before reuse
}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args, **pool_kwargs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
