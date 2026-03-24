from fastapi import FastAPI

from .database import engine
from .models import movie as movie_model
from .routers import movies

movie_model.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mov-Sug API", version="0.1.0")

app.include_router(movies.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Mov-Sug API"}
