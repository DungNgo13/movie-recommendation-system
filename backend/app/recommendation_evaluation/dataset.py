"""
MovieLens dataset loader, feature constructor, and leak-free chronological splitter.

Handles:
- Downloading and verifying MovieLens ml-latest-small
- Parsing movies.csv, ratings.csv, tags.csv
- Adapting metadata into TF-IDF text documents adhering to MovSug weighting rules
- Generating reproducible per-user chronological train/val/test splits without temporal leakage
- Calculating cryptographic checksums for raw files and splits
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import csv
import hashlib
import json
import os
import ssl
import urllib.request
import zipfile

import certifi


@dataclass
class MovieMetadata:
    """Represents a movie and its adapted text representation."""
    movie_id: str
    title: str
    genres: list[str]
    tags: list[str] = field(default_factory=list)
    text_profile: str = ""


@dataclass
class RatingEvent:
    """Represents a user-movie rating event with timestamp."""
    user_id: str
    movie_id: str
    rating: float
    timestamp: int


@dataclass
class EvaluationDataset:
    """Container holding full catalog and per-user split interactions."""
    movies: dict[str, MovieMetadata]
    train_by_user: dict[str, list[RatingEvent]]
    val_by_user: dict[str, list[RatingEvent]]
    test_by_user: dict[str, list[RatingEvent]]
    raw_files_checksum: str
    split_checksum: str
    total_ratings_count: int
    users_count: int
    movies_count: int


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_and_extract_movielens(
    dest_dir: Path,
    url: str = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip",
) -> tuple[Path, str]:
    """
    Download MovieLens ml-latest-small.zip if not present, verify, and extract.

    Returns:
        (extracted_folder_path, zip_sha256)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "ml-latest-small.zip"
    extracted_dir = dest_dir / "ml-latest-small"

    if not zip_path.exists():
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(url, context=ssl_ctx) as response, open(zip_path, "wb") as out_file:
            while chunk := response.read(65536):
                out_file.write(chunk)

    zip_sha256 = compute_file_sha256(zip_path)

    # Extract if extracted dir does not contain the required CSVs
    required_files = ["movies.csv", "ratings.csv", "tags.csv"]
    if not (extracted_dir.exists() and all((extracted_dir / f).exists() for f in required_files)):
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(dest_dir)

    return extracted_dir, zip_sha256


def build_movielens_text_profile(
    title: str,
    genres: list[str],
    tags: list[str],
    title_weight: int = 2,
    keywords_weight: int = 2,
    genres_weight: int = 1,
) -> str:
    """
    Construct text document according to MovSug movie_profile.py rules.

    Field weights (achieved through token repetition):
      - title    ×2  (primary identity)
      - keywords ×2  (tags in MovieLens serve as keywords, lowercased)
      - genres   ×1  (space-separated)
      - overview ×1  (not available in MovieLens, omitted)
      - cast     ×1  (not available in MovieLens, omitted)
      - director ×1  (not available in MovieLens, omitted)
    """
    parts: list[str] = []

    # Title × repetition
    if title:
        for _ in range(title_weight):
            parts.append(title)

    # Genres × repetition
    if genres:
        genre_str = " ".join(genres)
        for _ in range(genres_weight):
            parts.append(genre_str)

    # Tags / Keywords (lowercased) × repetition
    if tags:
        kw_str = " ".join(t.strip().lower() for t in tags if t.strip())
        if kw_str:
            for _ in range(keywords_weight):
                parts.append(kw_str)

    return " ".join(parts).strip()


def load_raw_movielens(
    dataset_dir: Path,
) -> tuple[dict[str, MovieMetadata], list[RatingEvent], dict[str, list[tuple[str, int]]], str]:
    """
    Load raw MovieLens CSV files into memory.

    Returns:
        (movies_dict, all_ratings, tags_by_movie, raw_files_checksum)
    """
    movies_path = dataset_dir / "movies.csv"
    ratings_path = dataset_dir / "ratings.csv"
    tags_path = dataset_dir / "tags.csv"

    if not (movies_path.exists() and ratings_path.exists() and tags_path.exists()):
        raise FileNotFoundError(f"Missing one or more required CSV files in {dataset_dir}")

    # Compute combined raw files checksum
    raw_hasher = hashlib.sha256()
    for p in (movies_path, ratings_path, tags_path):
        raw_hasher.update(compute_file_sha256(p).encode("utf-8"))
    raw_files_checksum = raw_hasher.hexdigest()

    # 1. Load tags: {movie_id: [(tag_text, timestamp), ...]}
    tags_by_movie: dict[str, list[tuple[str, int]]] = {}
    with open(tags_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mid = row["movieId"].strip()
            tag = row["tag"].strip().lower()
            ts = int(row["timestamp"])
            if mid not in tags_by_movie:
                tags_by_movie[mid] = []
            tags_by_movie[mid].append((tag, ts))

    # 2. Load movies
    movies: dict[str, MovieMetadata] = {}
    with open(movies_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mid = row["movieId"].strip()
            title = row["title"].strip()
            raw_genres = row.get("genres", "")
            genres = [
                g.strip()
                for g in raw_genres.split("|")
                if g.strip() and g != "(no genres listed)"
            ]
            movies[mid] = MovieMetadata(
                movie_id=mid,
                title=title,
                genres=genres,
                tags=[],
                text_profile="",
            )

    # 3. Load ratings
    ratings: list[RatingEvent] = []
    with open(ratings_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ratings.append(
                RatingEvent(
                    user_id=row["userId"].strip(),
                    movie_id=row["movieId"].strip(),
                    rating=float(row["rating"]),
                    timestamp=int(row["timestamp"]),
                )
            )

    return movies, ratings, tags_by_movie, raw_files_checksum


def per_user_chronological_split(
    ratings: list[RatingEvent],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    min_interactions: int = 5,
) -> tuple[dict[str, list[RatingEvent]], dict[str, list[RatingEvent]], dict[str, list[RatingEvent]], str]:
    """
    Partition each user's interactions chronologically into train, validation, and test.

    Enforces strictly:
      max(train.timestamp) <= min(val.timestamp) <= max(val.timestamp) <= min(test.timestamp)

    Returns:
        (train_by_user, val_by_user, test_by_user, split_checksum)
    """
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got {train_ratio + val_ratio + test_ratio}")

    # Group ratings by user
    user_ratings_map: dict[str, list[RatingEvent]] = {}
    for r in ratings:
        user_ratings_map.setdefault(r.user_id, []).append(r)

    train_by_user: dict[str, list[RatingEvent]] = {}
    val_by_user: dict[str, list[RatingEvent]] = {}
    test_by_user: dict[str, list[RatingEvent]] = {}

    split_hasher = hashlib.sha256()

    # Sort users deterministically
    sorted_user_ids = sorted(user_ratings_map.keys(), key=lambda uid: int(uid) if uid.isdigit() else uid)

    for uid in sorted_user_ids:
        u_ratings = user_ratings_map[uid]
        if len(u_ratings) < min_interactions:
            # Users with too few interactions are kept in train only
            train_by_user[uid] = u_ratings
            val_by_user[uid] = []
            test_by_user[uid] = []
            continue

        # Chronological sort: primary key = timestamp ASC, secondary key = movie_id ASC
        u_ratings_sorted = sorted(u_ratings, key=lambda x: (x.timestamp, int(x.movie_id) if x.movie_id.isdigit() else x.movie_id))

        total_u = len(u_ratings_sorted)
        n_train = max(1, int(total_u * train_ratio))
        n_val = int(total_u * val_ratio)
        n_test = total_u - n_train - n_val

        # Guard against zero test items if user has enough interactions
        if n_test == 0 and total_u >= 3:
            n_test = 1
            if n_train > 1:
                n_train -= 1
            elif n_val > 0:
                n_val -= 1

        u_train = u_ratings_sorted[:n_train]
        u_val = u_ratings_sorted[n_train : n_train + n_val]
        u_test = u_ratings_sorted[n_train + n_val :]

        # Strict temporal non-leakage verification
        if u_train and u_val:
            assert max(r.timestamp for r in u_train) <= min(r.timestamp for r in u_val), (
                f"Temporal leakage in user {uid}: train max > val min"
            )
        if u_val and u_test:
            assert max(r.timestamp for r in u_val) <= min(r.timestamp for r in u_test), (
                f"Temporal leakage in user {uid}: val max > test min"
            )
        if u_train and u_test and not u_val:
            assert max(r.timestamp for r in u_train) <= min(r.timestamp for r in u_test), (
                f"Temporal leakage in user {uid}: train max > test min"
            )

        train_by_user[uid] = u_train
        val_by_user[uid] = u_val
        test_by_user[uid] = u_test

        # Feed to split checksum
        split_hasher.update(f"{uid}:{len(u_train)}:{len(u_val)}:{len(u_test)};".encode("utf-8"))

    split_checksum = split_hasher.hexdigest()
    return train_by_user, val_by_user, test_by_user, split_checksum


def build_evaluation_dataset(
    dataset_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    min_interactions: int = 5,
    title_weight: int = 2,
    keywords_weight: int = 2,
    genres_weight: int = 1,
    tag_leakage_prevention: bool = True,
) -> EvaluationDataset:
    """
    Build the complete EvaluationDataset with leak-free text profiles and chronological splits.

    Leakage prevention:
      If tag_leakage_prevention is True, tags applied after the maximum training timestamp
      across the evaluation cohort are excluded from movie keywords to prevent future user
      interaction signals from leaking into movie content vectors.
    """
    movies, ratings, tags_by_movie, raw_checksum = load_raw_movielens(dataset_dir)

    train_by_user, val_by_user, test_by_user, split_checksum = per_user_chronological_split(
        ratings=ratings,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        min_interactions=min_interactions,
    )

    # Determine train horizon for tag leak prevention
    max_train_ts = 0
    if tag_leakage_prevention:
        for u_train in train_by_user.values():
            if u_train:
                max_train_ts = max(max_train_ts, max(r.timestamp for r in u_train))

    # Attach tags and generate text profile for each movie
    for mid, movie in movies.items():
        movie_tags_raw = tags_by_movie.get(mid, [])
        if tag_leakage_prevention and max_train_ts > 0:
            # Keep only tags applied before or at the global train horizon
            filtered_tags = [t for t, ts in movie_tags_raw if ts <= max_train_ts]
        else:
            filtered_tags = [t for t, _ in movie_tags_raw]

        # Deduplicate while preserving order
        seen_tags = set()
        dedup_tags = []
        for t in filtered_tags:
            if t not in seen_tags:
                seen_tags.add(t)
                dedup_tags.append(t)

        movie.tags = dedup_tags
        movie.text_profile = build_movielens_text_profile(
            title=movie.title,
            genres=movie.genres,
            tags=movie.tags,
            title_weight=title_weight,
            keywords_weight=keywords_weight,
            genres_weight=genres_weight,
        )

    return EvaluationDataset(
        movies=movies,
        train_by_user=train_by_user,
        val_by_user=val_by_user,
        test_by_user=test_by_user,
        raw_files_checksum=raw_checksum,
        split_checksum=split_checksum,
        total_ratings_count=len(ratings),
        users_count=len(train_by_user),
        movies_count=len(movies),
    )
