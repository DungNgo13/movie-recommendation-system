from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .models import movie as movie_model
from .routers import movies

movie_model.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mov-Sug API", version="0.1.0")

# Set up CORS
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(movies.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Mov-Sug API"}
