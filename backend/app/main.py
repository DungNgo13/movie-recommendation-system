from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

movie_model.Base.metadata.create_all(bind=engine)
user_model.Base.metadata.create_all(bind=engine)
user_favorite_model.Base.metadata.create_all(bind=engine)
watch_history_model.Base.metadata.create_all(bind=engine)
rating_model.Base.metadata.create_all(bind=engine)
admin_audit_log_model.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mov-Sug API", version="0.1.0")

# Set up CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

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
app.include_router(ratings.router)
app.include_router(recommendations.router)
app.include_router(admin_users.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_logs.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Mov-Sug API"}

