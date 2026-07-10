from datetime import datetime, timedelta, timezone
import bcrypt
import os
from jose import jwt, JWTError
from dotenv import load_dotenv

load_dotenv()

# SECRET_KEY MUST be set in the environment (via .env or OS env vars).
# No fallback — a missing or empty key is a fatal configuration error.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise RuntimeError(
        "FATAL: SECRET_KEY environment variable is not set or is empty. "
        "Create a backend/.env file with a strong random SECRET_KEY value. "
        "See backend/.env.example for the expected format."
    )
ALGORITHM = "HS256"
try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))
except ValueError:
    ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours (sliding session extends on activity)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_short_lived_token(data: dict, expire_minutes: int = 15) -> str:
    """Create a short-lived JWT for one-time actions (e.g. password change confirmation)."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
