import logging
from datetime import date
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.movie import Movie

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample movie data
MOVIES = [
    {
        "title": "Inception",
        "overview": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
        "release_date": date(2010, 7, 16),
        "genres": ["Action", "Science Fiction", "Thriller"],
        "director": "Christopher Nolan",
        "poster_url": "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkWTkvHsgtKA40av.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/s3TBrA1U1soXEliACLmG3UsINa.jpg",
    },
    {
        "title": "The Shawshank Redemption",
        "overview": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.",
        "release_date": date(1994, 9, 23),
        "genres": ["Drama", "Crime"],
        "director": "Frank Darabont",
        "poster_url": "https://image.tmdb.org/t/p/w500/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/kXm4QZ3srfhighlightColor.jpg",
    },
    {
        "title": "The Godfather",
        "overview": "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant son.",
        "release_date": date(1972, 3, 14),
        "genres": ["Drama", "Crime"],
        "director": "Francis Ford Coppola",
        "poster_url": "https://image.tmdb.org/t/p/w500/3bhkrj58Vtu7enYsRolD1fZdja1.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/tmU7GeKVybMWFButWEGl2M4GeiU.jpg",
    },
    {
        "title": "Parasite",
        "overview": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
        "release_date": date(2019, 5, 30),
        "genres": ["Comedy", "Thriller", "Drama"],
        "director": "Bong Joon Ho",
        "poster_url": "https://image.tmdb.org/t/p/w500/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/ApiBzeaa95TNYliSbQ8pJv4Fje7.jpg",
    },
    {
        "title": "Interstellar",
        "overview": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
        "release_date": date(2014, 11, 5),
        "genres": ["Adventure", "Drama", "Science Fiction"],
        "director": "Christopher Nolan",
        "poster_url": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/xJHokMbljvjADYdit5fK5VQsXEG.jpg",
    },
    {
        "title": "Pulp Fiction",
        "overview": "A burger-loving hitman, his philosophical partner, a drug-addled gangster's moll and a washed-up boxer converge in this sprawling, comedic crime caper.",
        "release_date": date(1994, 10, 14),
        "genres": ["Thriller", "Crime"],
        "director": "Quentin Tarantino",
        "poster_url": "https://image.tmdb.org/t/p/w500/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/suaEOtk1N1sgg2MTM7oZd2cfVp3.jpg",
    },
    {
        "title": "The Dark Knight",
        "overview": "When the menace known as the Joker emerges from his mysterious past, he wreaks havoc and chaos on the people of Gotham.",
        "release_date": date(2008, 7, 18),
        "genres": ["Drama", "Action", "Crime", "Thriller"],
        "director": "Christopher Nolan",
        "poster_url": "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/dqK9Hag1054tghRQSqLSfrkvQnA.jpg",
    },
    {
        "title": "Forrest Gump",
        "overview": "A man with a low IQ has accomplished great things in his life and been present during significant historic events—in each case, far exceeding what anyone imagined he could do.",
        "release_date": date(1994, 7, 6),
        "genres": ["Comedy", "Drama", "Romance"],
        "director": "Robert Zemeckis",
        "poster_url": "https://image.tmdb.org/t/p/w500/arw2vcBveWOVZr6pxd9XTd1TdSm.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/7c_adM0eo6D2d5x4s0l4i0H2N28.jpg",
    },
        {
        "title": "Spirited Away",
        "overview": "A young girl, Chihiro, becomes trapped in a strange new world of spirits. When her parents undergo a mysterious transformation, she must call upon the courage she never knew she had to free her family.",
        "release_date": date(2001, 7, 20),
        "genres": ["Animation", "Family", "Fantasy"],
        "director": "Hayao Miyazaki",
        "poster_url": "https://image.tmdb.org/t/p/w500/39wmItIW2asRMyTEkS9LhplA6Ui.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/mGhd3sySt2aWq4y4iQ8L3DPs2a.jpg",
    },
    {
        "title": "The Matrix",
        "overview": "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers.",
        "release_date": date(1999, 3, 31),
        "genres": ["Action", "Science Fiction"],
        "director": "Lana Wachowski, Lilly Wachowski",
        "poster_url": "https://image.tmdb.org/t/p/w500/f89JxwIh8ARZNBBCcpewbJ6tmpH.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/rAiYTfKGqDCRIIqo664sY9XZIvQ.jpg",
    },
    {
        "title": "GoodFellas",
        "overview": "The story of Henry Hill and his life in the mob, covering his relationship with his wife Karen Hill and his mob partners Jimmy Conway and Tommy DeVito in the Italian-American crime syndicate.",
        "release_date": date(1990, 9, 12),
        "genres": ["Drama", "Crime"],
        "director": "Martin Scorsese",
        "poster_url": "https://image.tmdb.org/t/p/w500/aKuFiU82s5ISJpGZp7YkI9dUYIp.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/sw7mordYZrYKxGrLriggYtoqxS.jpg",
    },
    {
        "title": "Fight Club",
        "overview": "An insomniac office worker looking for a way to change his life crosses paths with a devil-may-care soap maker and they form an underground fight club that evolves into something much, much more.",
        "release_date": date(1999, 10, 15),
        "genres": ["Drama"],
        "director": "David Fincher",
        "poster_url": "https://image.tmdb.org/t/p/w500/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w1280/hZkgoQYus5vegHoetLkJoBvHiSa.jpg",
    }
]

def seed_movies(db: Session):
    """
    Seeds the database with an initial set of movies.
    Checks for existing movies by title to avoid duplicates.
    """
    logger.info("Starting to seed movies...")
    
    existing_movie_titles = {movie.title for movie in db.query(Movie.title).all()}
    
    movies_to_add = []
    for movie_data in MOVIES:
        if movie_data["title"] not in existing_movie_titles:
            movies_to_add.append(Movie(**movie_data))
            logger.info(f"Queueing movie for insertion: {movie_data['title']}")
        else:
            logger.info(f"Skipping existing movie: {movie_data['title']}")

    if not movies_to_add:
        logger.info("No new movies to add. Database is already seeded.")
        return

    try:
        db.add_all(movies_to_add)
        db.commit()
        logger.info(f"Successfully added {len(movies_to_add)} new movies to the database.")
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        db.rollback()

if __name__ == "__main__":
    logger.info("Creating database session for seeding.")
    db = SessionLocal()
    try:
        seed_movies(db)
    finally:
        logger.info("Closing database session.")
        db.close()

