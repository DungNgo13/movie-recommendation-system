import os
import asyncio
import contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load .env FIRST — before any module reads os.getenv().
load_dotenv()

from .database import engine
from .models import movie as movie_model
from .models import user as user_model
from .models import user_favorite as user_favorite_model
from .models import watch_history as watch_history_model
from .models import rating as rating_model
from .models import admin_audit_log as admin_audit_log_model
from .routers import movies
from .routers import auth
from .routers import favorites
from .routers import history
from .routers import ratings
from .routers import recommendations
from .routers import admin_users
from .routers import admin_dashboard
from .routers import admin_logs
from .routers import admin_recommendations
from .routers import watch_progress

movie_model.Base.metadata.create_all(bind=engine)
user_model.Base.metadata.create_all(bind=engine)
user_favorite_model.Base.metadata.create_all(bind=engine)
watch_history_model.Base.metadata.create_all(bind=engine)
rating_model.Base.metadata.create_all(bind=engine)
admin_audit_log_model.Base.metadata.create_all(bind=engine)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    STARTUP  → launch the singleton encoding worker so exactly one FFmpeg
               process can run at a time (prevents CPU exhaustion).
    SHUTDOWN → cancel the worker task gracefully.

    Using lifespan instead of the deprecated @app.on_event("startup") is the
    recommended pattern since FastAPI 0.93.
    """
    from .services.hls_service import encoding_worker   # local import avoids circular deps

    worker_task = asyncio.create_task(encoding_worker(), name="hls_encoding_worker")

    yield   # ←── application runs here ────────────────────────────────────

    # SHUTDOWN: cancel the worker and wait for it to finish cleanly.
    worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker_task


app = FastAPI(title="Mov-Sug API", version="0.1.0", lifespan=lifespan)


# Legacy mount mapping for historical files strictly ensuring backwards-parsing safely
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# New explicit media mapping bridging phase limits locally structuring natively!
os.makedirs("media/images/posters", exist_ok=True)
os.makedirs("media/images/backdrops", exist_ok=True)
os.makedirs("media/videos/source", exist_ok=True)
os.makedirs("media/videos/hls", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Read allowed origins from the CORS_ORIGINS env var (comma-separated).
# Falls back to localhost dev defaults if not set.
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(movies.router)
app.include_router(auth.router)
app.include_router(favorites.router)
app.include_router(history.router)
app.include_router(watch_progress.router)
app.include_router(ratings.router)
app.include_router(recommendations.router)
app.include_router(admin_users.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_logs.router)
app.include_router(admin_recommendations.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Mov-Sug API"}
