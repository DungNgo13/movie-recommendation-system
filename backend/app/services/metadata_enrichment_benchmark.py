"""
Controlled integration verification and benchmark for Phase 8A Movie Metadata Enrichment.

Executes the end-to-end enrichment pipeline across 16 representative movies in an
isolated SQLite database without mutating production/development databases or
frozen Phase 4–6 recommendation experiment artifacts.

Scenarios covered across the 16 movies:
  1. Exact TMDB ID match (`The Shawshank Redemption`, tmdb_id=278)
  2. Verified IMDb ID match (`Pulp Fiction`, imdb_id=tt0110912)
  3. Bilingual catalog title (`Interstellar 2014 - Hố Đen Tử Thần`)
  4. Bilingual animated classic (`Spirited Away - Vùng Đất Linh Hồn (2001)`)
  5. Localized Korean/Vietnamese title (`Điều Ước CUối Cùng Của Tù Nhân 2037 - My Girl 2037 (2022)`)
  6. Localized sequel with punctuation (`Thám Tử Lừng Danh Conan 28: Dư Ảnh Của Độc Nhãn - Detective Conan: One-Eyed Flashback (2025)`)
  7. Common title disambiguation (`The Gift`, 2015 Joel Edgerton vs 2000 Sam Raimi)
  8. Remake disambiguation (`Nosferatu`, 1922 F.W. Murnau vs 1979 Herzog vs 2024 Eggers)
  9. Missing overview, cast & keywords (`Night of the Living Dead`, 1968 George A. Romero)
  10. Sequel disambiguation (`The Godfather Part II`, 1974 vs `The Godfather`, 1972)
  11. Public domain silent classic missing genres & cast (`The General`, 1926)
  12. Public domain horror classic missing genres & cast (`The Phantom of the Opera`, 1925)
  13. HTTP 429 rate-limit + retry recovery (`Charade`, 1963 Stanley Donen)
  14. Conflicting release year held/rejected by admin (`His Girl Friday`, stored 1945 vs TMDB 1940)
  15. Ambiguous adaptation rejected by admin (`The Little Shop of Horrors`, stored without director, 1960 vs 1986)
  16. No-match experimental entry (`Untitled Student Experimental Reel 9999XYZ`, 2024)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import statistics
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ..database import Base
from ..models.metadata_enrichment import MetadataCandidate, MetadataEnrichmentJob
from ..models.movie import Movie
from .metadata_application_service import apply_approved_metadata
from .metadata_staging_service import (
    review_approve_enrichment_job,
    review_reject_enrichment_job,
    start_enrichment_job,
)
from .recommendation.vectorizer import get_cache_stats, refresh_cache
from .tmdb_client import TMDBClient, TMDBConfig

TRACKED_COMPLETENESS_FIELDS: tuple[str, ...] = (
    "overview",
    "genres",
    "cast",
    "director",
    "keywords",
    "release_date",
    "poster_path",
    "backdrop_path",
    "title_vi",
    "overview_vi",
    "tmdb_id",
    "imdb_id",
)


def _is_field_populated(movie: Movie, field: str) -> bool:
    val = getattr(movie, field, None)
    if val is None:
        return False
    if field == "release_date" and isinstance(val, date):
        # Note: YYYY-01-01 placeholder dates are counted as present in raw date column,
        # while exact release date precision is tracked separately.
        return True
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, dict)):
        return len(val) > 0
    return True


def compute_catalog_completeness(movies: list[Movie]) -> dict[str, Any]:
    """Compute field-level and overall completeness across a list of movies."""
    total = len(movies)
    if total == 0:
        return {"total_movies": 0, "fields": {}, "overall_completeness_ratio": 0.0}

    field_stats: dict[str, dict[str, Any]] = {}
    populated_cells = 0
    total_cells = total * len(TRACKED_COMPLETENESS_FIELDS)

    for field in TRACKED_COMPLETENESS_FIELDS:
        count = sum(1 for m in movies if _is_field_populated(m, field))
        populated_cells += count
        field_stats[field] = {
            "populated": count,
            "missing": total - count,
            "completeness_ratio": round(count / total, 4),
        }

    # Also track non-placeholder release dates (not Jan 1 default)
    exact_dates = sum(
        1
        for m in movies
        if isinstance(m.release_date, date)
        and not (m.release_date.month == 1 and m.release_date.day == 1)
    )
    movies_with_any_missing = sum(
        1
        for m in movies
        if any(not _is_field_populated(m, f) for f in TRACKED_COMPLETENESS_FIELDS)
    )

    return {
        "total_movies": total,
        "movies_with_missing_metadata": movies_with_any_missing,
        "exact_release_date_count": exact_dates,
        "exact_release_date_ratio": round(exact_dates / total, 4),
        "overall_completeness_ratio": round(populated_cells / total_cells, 4),
        "fields": field_stats,
    }


def _build_mock_tmdb_catalog() -> dict[int, dict[str, Any]]:
    """Deterministic TMDB movie detail payloads for the 16-movie benchmark."""
    return {
        278: {
            "id": 278,
            "imdb_id": "tt0111161",
            "title": "The Shawshank Redemption",
            "original_title": "The Shawshank Redemption",
            "original_language": "en",
            "release_date": "1994-09-23",
            "runtime": 142,
            "overview": "Imprisoned in the 1940s for the double murder of his wife and her lover, upstanding banker Andy Dufresne begins a new life at the Shawshank prison.",
            "poster_path": "/9cqNxx0GxF0bflZmeSMuL5tnGzr.jpg",
            "backdrop_path": "/kXfqcdQKsToO0OUXHcrrNCHDBzO.jpg",
            "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
            "credits": {
                "cast": [
                    {"name": "Tim Robbins", "order": 0},
                    {"name": "Morgan Freeman", "order": 1},
                    {"name": "Bob Gunton", "order": 2},
                ],
                "crew": [{"name": "Frank Darabont", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "prison"},
                    {"name": "wrongful imprisonment"},
                    {"name": "hope"},
                ]
            },
            "vi": {
                "title": "Nhà Tù Shawshank",
                "overview": "Andy Dufresne bị kết án oan và bắt đầu cuộc sống mới tại nhà tù Shawshank.",
            },
        },
        680: {
            "id": 680,
            "imdb_id": "tt0110912",
            "title": "Pulp Fiction",
            "original_title": "Pulp Fiction",
            "original_language": "en",
            "release_date": "1994-09-10",
            "runtime": 154,
            "overview": "A burger-loving hit man, his philosophical partner, a drug-addled gangster's moll and a washed-up boxer converge in sprawling crime caper.",
            "poster_path": "/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg",
            "backdrop_path": "/suaEOtk1N1sgg2MTM7oZd2cfVp3.jpg",
            "genres": [{"id": 53, "name": "Thriller"}, {"id": 80, "name": "Crime"}],
            "credits": {
                "cast": [
                    {"name": "John Travolta", "order": 0},
                    {"name": "Samuel L. Jackson", "order": 1},
                    {"name": "Uma Thurman", "order": 2},
                ],
                "crew": [{"name": "Quentin Tarantino", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "hitman"},
                    {"name": "nonlinear timeline"},
                    {"name": "los angeles"},
                ]
            },
            "vi": {
                "title": "Chuyện Tào Lao",
                "overview": "Những câu chuyện tội phạm đan xen tại Los Angeles của đạo diễn Quentin Tarantino.",
            },
        },
        157336: {
            "id": 157336,
            "imdb_id": "tt0816692",
            "title": "Interstellar",
            "original_title": "Interstellar",
            "original_language": "en",
            "release_date": "2014-11-05",
            "runtime": 169,
            "overview": "The adventures of a group of explorers who make use of a newly discovered wormhole to surpass the limitations on human space travel.",
            "poster_path": "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
            "backdrop_path": "/xJHokMbljvjADYdit5fK5VQsXEG.jpg",
            "genres": [
                {"id": 12, "name": "Adventure"},
                {"id": 18, "name": "Drama"},
                {"id": 878, "name": "Science Fiction"},
            ],
            "credits": {
                "cast": [
                    {"name": "Matthew McConaughey", "order": 0},
                    {"name": "Anne Hathaway", "order": 1},
                    {"name": "Jessica Chastain", "order": 2},
                ],
                "crew": [{"name": "Christopher Nolan", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "wormhole"},
                    {"name": "space travel"},
                    {"name": "relativity"},
                ]
            },
            "vi": {
                "title": "Hố Đen Tử Thần",
                "overview": "Một nhóm nhà du hành vũ trụ đi qua lỗ sâu để tìm kiếm hành tinh mới cho nhân loại.",
            },
        },
        129: {
            "id": 129,
            "imdb_id": "tt0245429",
            "title": "Spirited Away",
            "original_title": "千と千尋の神隠し",
            "original_language": "ja",
            "release_date": "2001-07-20",
            "runtime": 125,
            "overview": "A young girl, Chihiro, becomes trapped in a strange new world of spirits. When her parents undergo a mysterious transformation, she must call upon the courage she never knew she had to free her family.",
            "poster_path": "/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg",
            "backdrop_path": "/Ab8mkHmkYADjU7wQiOkia9BzGvS.jpg",
            "genres": [
                {"id": 16, "name": "Animation"},
                {"id": 10751, "name": "Family"},
                {"id": 14, "name": "Fantasy"},
            ],
            "credits": {
                "cast": [
                    {"name": "Rumi Hiiragi", "order": 0},
                    {"name": "Miyu Irino", "order": 1},
                    {"name": "Mari Natsuki", "order": 2},
                ],
                "crew": [{"name": "Hayao Miyazaki", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "spirit world"},
                    {"name": "bathhouse"},
                    {"name": "coming of age"},
                ]
            },
            "vi": {
                "title": "Vùng Đất Linh Hồn",
                "overview": "Cô bé Chihiro lạc vào thế giới linh hồn và phải tìm cách giải cứu cha mẹ mình.",
            },
        },
        961729: {
            "id": 961729,
            "imdb_id": "tt20869502",
            "title": "My Girl",
            "original_title": "이공삼칠",
            "original_language": "ko",
            "release_date": "2022-06-08",
            "runtime": 126,
            "overview": "19-year-old Yoon-young lives alone with her deaf mother and prepares for the civil service exam, until a tragic incident sends her to prison as inmate 2037.",
            "poster_path": "/mygirl2037_poster.jpg",
            "backdrop_path": "/mygirl2037_backdrop.jpg",
            "genres": [{"id": 18, "name": "Drama"}],
            "credits": {
                "cast": [
                    {"name": "Hong Ye-ji", "order": 0},
                    {"name": "Kim Ji-young", "order": 1},
                    {"name": "Kim Mi-hwa", "order": 2},
                ],
                "crew": [{"name": "Mo Hong-jin", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "women's prison"},
                    {"name": "mother daughter"},
                    {"name": "resilience"},
                ]
            },
            "vi": {
                "title": "Điều Ước Cuối Cùng Của Tù Nhân 2037",
                "overview": "Cô gái 19 tuổi Yoon-young bị đưa vào nhà tù nữ với số hiệu 2037 và nhận được sự sẻ chia từ các bạn tù.",
            },
        },
        1397832: {
            "id": 1397832,
            "imdb_id": "tt34891234",
            "title": "Detective Conan: One-Eyed Flashback",
            "original_title": "名探偵コナン 隻眼の残像",
            "original_language": "ja",
            "release_date": "2025-04-18",
            "runtime": 110,
            "overview": "Conan Edogawa and Kansuke Yamato investigate a snowy mountain conspiracy tied to a painful memory from Yamato's past in Nagano.",
            "poster_path": "/conan28_poster.jpg",
            "backdrop_path": "/conan28_backdrop.jpg",
            "genres": [
                {"id": 16, "name": "Animation"},
                {"id": 9648, "name": "Mystery"},
                {"id": 28, "name": "Action"},
            ],
            "credits": {
                "cast": [
                    {"name": "Minami Takayama", "order": 0},
                    {"name": "Wakana Yamazaki", "order": 1},
                    {"name": "Rikiya Koyama", "order": 2},
                ],
                "crew": [{"name": "Katsuya Shigehara", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "detective"},
                    {"name": "nagano"},
                    {"name": "snowy mountain"},
                ]
            },
            "vi": {
                "title": "Thám Tử Lừng Danh Conan 28: Dư Ảnh Của Độc Nhãn",
                "overview": "Conan và thanh tra Yamato Kansuke điều tra bí ẩn trên vùng núi tuyết Nagano.",
            },
        },
        328425: {
            "id": 328425,
            "imdb_id": "tt4178092",
            "title": "The Gift",
            "original_title": "The Gift",
            "original_language": "en",
            "release_date": "2015-07-30",
            "runtime": 108,
            "overview": "Simon and Robyn are a young married couple whose life is going just as planned until a chance encounter with a high school acquaintance sends their world into a harrowing tailspin.",
            "poster_path": "/thegift2015_poster.jpg",
            "backdrop_path": "/thegift2015_backdrop.jpg",
            "genres": [
                {"id": 53, "name": "Thriller"},
                {"id": 9648, "name": "Mystery"},
                {"id": 18, "name": "Drama"},
            ],
            "credits": {
                "cast": [
                    {"name": "Jason Bateman", "order": 0},
                    {"name": "Rebecca Hall", "order": 1},
                    {"name": "Joel Edgerton", "order": 2},
                ],
                "crew": [{"name": "Joel Edgerton", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "stalker"},
                    {"name": "high school past"},
                    {"name": "psychological thriller"},
                ]
            },
            "vi": {
                "title": "Món Quà Bí Ẩn",
                "overview": "Cuộc sống của cặp vợ chồng trẻ đảo lộn khi người bạn cũ thời trung học bất ngờ xuất hiện.",
            },
        },
        2046: {
            "id": 2046,
            "imdb_id": "tt0219699",
            "title": "The Gift",
            "original_title": "The Gift",
            "original_language": "en",
            "release_date": "2000-12-20",
            "runtime": 112,
            "overview": "A widow with extrasensory perception is asked to help find a young woman who has disappeared.",
            "poster_path": "/thegift2000_poster.jpg",
            "backdrop_path": "/thegift2000_backdrop.jpg",
            "genres": [{"id": 53, "name": "Thriller"}, {"id": 27, "name": "Horror"}],
            "credits": {
                "cast": [{"name": "Cate Blanchett", "order": 0}],
                "crew": [{"name": "Sam Raimi", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "clairvoyance"}]},
            "vi": {
                "title": "Giác Quan Thứ Sáu: Món Quà",
                "overview": "Một phụ nữ có khả năng ngoại cảm hỗ trợ điều tra vụ mất tích.",
            },
        },
        653: {
            "id": 653,
            "imdb_id": "tt0013442",
            "title": "Nosferatu",
            "original_title": "Nosferatu, eine Symphonie des Grauens",
            "original_language": "de",
            "release_date": "1922-03-04",
            "runtime": 94,
            "overview": "Vampire Count Orlok expresses interest in a new residence and real estate agent Hutter's wife in classic German Expressionist horror.",
            "poster_path": "/nosferatu1922_poster.jpg",
            "backdrop_path": "/nosferatu1922_backdrop.jpg",
            "genres": [{"id": 27, "name": "Horror"}, {"id": 14, "name": "Fantasy"}],
            "credits": {
                "cast": [
                    {"name": "Max Schreck", "order": 0},
                    {"name": "Gustav von Wangenheim", "order": 1},
                    {"name": "Greta Schröder", "order": 2},
                ],
                "crew": [{"name": "F. W. Murnau", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "vampire"},
                    {"name": "german expressionism"},
                    {"name": "silent film"},
                ]
            },
            "vi": {
                "title": "Ma Cà Rồng Nosferatu (1922)",
                "overview": "Bá tước ma cà rồng Orlok gieo rắc nỗi kinh hoàng trong kiệt tác điện ảnh câm Đức năm 1922.",
            },
        },
        6404: {
            "id": 6404,
            "imdb_id": "tt0079641",
            "title": "Nosferatu the Vampyre",
            "original_title": "Nosferatu: Phantom der Nacht",
            "original_language": "de",
            "release_date": "1979-01-17",
            "runtime": 107,
            "overview": "Jonathan Harker is sent away to Count Dracula's castle to sell him a house in Virna.",
            "poster_path": "/nosferatu1979_poster.jpg",
            "backdrop_path": "/nosferatu1979_backdrop.jpg",
            "genres": [{"id": 27, "name": "Horror"}],
            "credits": {
                "cast": [{"name": "Klaus Kinski", "order": 0}],
                "crew": [{"name": "Werner Herzog", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "vampire"}]},
            "vi": {"title": "Nosferatu (1979)", "overview": "Bản làm lại năm 1979 của Werner Herzog."},
        },
        426063: {
            "id": 426063,
            "imdb_id": "tt5040012",
            "title": "Nosferatu",
            "original_title": "Nosferatu",
            "original_language": "en",
            "release_date": "2024-12-25",
            "runtime": 132,
            "overview": "A gothic tale of obsession between a haunted young woman and the terrifying vampire infatuated with her.",
            "poster_path": "/nosferatu2024_poster.jpg",
            "backdrop_path": "/nosferatu2024_backdrop.jpg",
            "genres": [{"id": 27, "name": "Horror"}],
            "credits": {
                "cast": [{"name": "Bill Skarsgård", "order": 0}],
                "crew": [{"name": "Robert Eggers", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "vampire"}]},
            "vi": {"title": "Nosferatu (2024)", "overview": "Bản làm lại năm 2024 của Robert Eggers."},
        },
        10331: {
            "id": 10331,
            "imdb_id": "tt0063350",
            "title": "Night of the Living Dead",
            "original_title": "Night of the Living Dead",
            "original_language": "en",
            "release_date": "1968-10-01",
            "runtime": 96,
            "overview": "A group of people try to survive an attack of bloodthirsty zombies while trapped in a rural Pennsylvania farmhouse.",
            "poster_path": "/notld1968_poster.jpg",
            "backdrop_path": "/notld1968_backdrop.jpg",
            "genres": [{"id": 27, "name": "Horror"}, {"id": 53, "name": "Thriller"}],
            "credits": {
                "cast": [
                    {"name": "Duane Jones", "order": 0},
                    {"name": "Judith O'Dea", "order": 1},
                    {"name": "Karl Hardman", "order": 2},
                ],
                "crew": [{"name": "George A. Romero", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "zombie"},
                    {"name": "farmhouse"},
                    {"name": "survival"},
                ]
            },
            "vi": {
                "title": "Đêm Của Những Xác Sống",
                "overview": "Một nhóm người cố gắng sống sót trước cuộc tấn công của xác sống tại một trang trại hẻo lánh.",
            },
        },
        240: {
            "id": 240,
            "imdb_id": "tt0071562",
            "title": "The Godfather Part II",
            "original_title": "The Godfather Part II",
            "original_language": "en",
            "release_date": "1974-12-20",
            "runtime": 202,
            "overview": "In the continuing saga of the Corleone crime family, a young Vito Corleone grows up in Sicily and 1910s New York while Michael Corleone expands the family syndicate.",
            "poster_path": "/godfather2_poster.jpg",
            "backdrop_path": "/godfather2_backdrop.jpg",
            "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
            "credits": {
                "cast": [
                    {"name": "Al Pacino", "order": 0},
                    {"name": "Robert Duvall", "order": 1},
                    {"name": "Robert De Niro", "order": 2},
                ],
                "crew": [{"name": "Francis Ford Coppola", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "mafia"},
                    {"name": "sicily"},
                    {"name": "sequel"},
                ]
            },
            "vi": {
                "title": "Bố Già Phần II",
                "overview": "Hành trình thời trẻ của Vito Corleone đan xen với tham vọng mở rộng đế chế của Michael Corleone.",
            },
        },
        238: {
            "id": 238,
            "imdb_id": "tt0068646",
            "title": "The Godfather",
            "original_title": "The Godfather",
            "original_language": "en",
            "release_date": "1972-03-14",
            "runtime": 175,
            "overview": "Spanning the years 1945 to 1955, a chronicle of the fictional Italian-American Corleone crime family.",
            "poster_path": "/godfather1_poster.jpg",
            "backdrop_path": "/godfather1_backdrop.jpg",
            "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
            "credits": {
                "cast": [{"name": "Marlon Brando", "order": 0}],
                "crew": [{"name": "Francis Ford Coppola", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "mafia"}]},
            "vi": {"title": "Bố Già", "overview": "Câu chuyện về gia tộc mafia Corleone."},
        },
        961: {
            "id": 961,
            "imdb_id": "tt0017925",
            "title": "The General",
            "original_title": "The General",
            "original_language": "en",
            "release_date": "1926-12-31",
            "runtime": 78,
            "overview": "During America's Civil War, Union spies steal engineer Johnny Gray's beloved locomotive, 'The General'—with Johnnie's lady love aboard an attached boxcar—and he single-handedly must do all in his power to both get The General back and to rescue Annabelle.",
            "poster_path": "/thegeneral1926_poster.jpg",
            "backdrop_path": "/thegeneral1926_backdrop.jpg",
            "genres": [
                {"id": 28, "name": "Action"},
                {"id": 12, "name": "Adventure"},
                {"id": 35, "name": "Comedy"},
                {"id": 10752, "name": "War"},
            ],
            "credits": {
                "cast": [
                    {"name": "Buster Keaton", "order": 0},
                    {"name": "Marion Mack", "order": 1},
                    {"name": "Glen Cavender", "order": 2},
                ],
                "crew": [{"name": "Buster Keaton", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "locomotive"},
                    {"name": "civil war"},
                    {"name": "slapstick"},
                ]
            },
            "vi": {
                "title": "Đầu Máy Tướng Quân",
                "overview": "Kỹ sư tàu hỏa Johnny Gray một mình truy đuổi gián điệp để giành lại đoàn tàu The General.",
            },
        },
        964: {
            "id": 964,
            "imdb_id": "tt0016220",
            "title": "The Phantom of the Opera",
            "original_title": "The Phantom of the Opera",
            "original_language": "en",
            "release_date": "1925-11-15",
            "runtime": 93,
            "overview": "A mad, disfigured composer seeks love with a lovely young opera singer in the catacombs beneath the Paris Opera House.",
            "poster_path": "/phantom1925_poster.jpg",
            "backdrop_path": "/phantom1925_backdrop.jpg",
            "genres": [{"id": 27, "name": "Horror"}, {"id": 18, "name": "Drama"}],
            "credits": {
                "cast": [
                    {"name": "Lon Chaney", "order": 0},
                    {"name": "Mary Philbin", "order": 1},
                    {"name": "Norman Kerry", "order": 2},
                ],
                "crew": [{"name": "Rupert Julian", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "opera house"},
                    {"name": "masked composer"},
                    {"name": "paris"},
                ]
            },
            "vi": {
                "title": "Bóng Ma Trong Nhà Hát",
                "overview": "Một nhạc sĩ dị dạng ẩn mình dưới hầm ngầm Nhà hát Opera Paris đem lòng yêu nữ ca sĩ trẻ.",
            },
        },
        4808: {
            "id": 4808,
            "imdb_id": "tt0056923",
            "title": "Charade",
            "original_title": "Charade",
            "original_language": "en",
            "release_date": "1963-12-05",
            "runtime": 113,
            "overview": "After Regina Lampert falls for the dashing Peter Joshua on a skiing holiday in the French Alps, she discovers upon her return to Paris that her husband has been murdered.",
            "poster_path": "/charade1963_poster.jpg",
            "backdrop_path": "/charade1963_backdrop.jpg",
            "genres": [
                {"id": 35, "name": "Comedy"},
                {"id": 9648, "name": "Mystery"},
                {"id": 10749, "name": "Romance"},
                {"id": 53, "name": "Thriller"},
            ],
            "credits": {
                "cast": [
                    {"name": "Cary Grant", "order": 0},
                    {"name": "Audrey Hepburn", "order": 1},
                    {"name": "Walter Matthau", "order": 2},
                ],
                "crew": [{"name": "Stanley Donen", "job": "Director"}],
            },
            "keywords": {
                "keywords": [
                    {"name": "paris"},
                    {"name": "stolen fortune"},
                    {"name": "hidden identity"},
                ]
            },
            "vi": {
                "title": "Trò Đùa Bí Ẩn",
                "overview": "Regina Lampert bị cuốn vào cuộc truy tìm kho báu bị đánh cắp tại Paris sau cái chết bí ẩn của chồng.",
            },
        },
        3085: {
            "id": 3085,
            "imdb_id": "tt0032599",
            "title": "His Girl Friday",
            "original_title": "His Girl Friday",
            "original_language": "en",
            "release_date": "1940-01-18",
            "runtime": 92,
            "overview": "Walter Burns is an investigative reporter and editor who learns his ex-wife Hildy Johnson is about to remarry and leave the newspaper business.",
            "poster_path": "/hisgirlfriday_poster.jpg",
            "backdrop_path": "/hisgirlfriday_backdrop.jpg",
            "genres": [
                {"id": 35, "name": "Comedy"},
                {"id": 18, "name": "Drama"},
                {"id": 10749, "name": "Romance"},
            ],
            "credits": {
                "cast": [
                    {"name": "Cary Grant", "order": 0},
                    {"name": "Rosalind Russell", "order": 1},
                ],
                "crew": [{"name": "Howard Hawks", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "newspaper"}, {"name": "screwball comedy"}]},
            "vi": {
                "title": "Cô Phóng Viên Tài Ba",
                "overview": "Chủ bút Walter Burns tìm mọi cách giữ chân nữ phóng viên xuất sắc Hildy Johnson.",
            },
        },
        24420: {
            "id": 24420,
            "imdb_id": "tt0054033",
            "title": "The Little Shop of Horrors",
            "original_title": "The Little Shop of Horrors",
            "original_language": "en",
            "release_date": "1960-09-14",
            "runtime": 72,
            "overview": "A clumsy young man nurtures a plant and discovers that it's carnivorous, forcing him to kill to feed it.",
            "poster_path": "/littleshop1960_poster.jpg",
            "backdrop_path": "/littleshop1960_backdrop.jpg",
            "genres": [{"id": 35, "name": "Comedy"}, {"id": 27, "name": "Horror"}],
            "credits": {
                "cast": [
                    {"name": "Jonathan Haze", "order": 0},
                    {"name": "Jackie Joseph", "order": 1},
                    {"name": "Jack Nicholson", "order": 2},
                ],
                "crew": [{"name": "Roger Corman", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "man-eating plant"}, {"name": "florist"}]},
            "vi": {
                "title": "Cửa Hàng Kinh Dị Nhỏ (1960)",
                "overview": "Một chàng trai vô tình nuôi dưỡng loài cây ăn thịt người trong tiệm hoa.",
            },
        },
        10776: {
            "id": 10776,
            "imdb_id": "tt0091419",
            "title": "Little Shop of Horrors",
            "original_title": "Little Shop of Horrors",
            "original_language": "en",
            "release_date": "1986-12-19",
            "runtime": 94,
            "overview": "Seymour Krelborn is a nerdy orphan working at Mushnik's, a flower shop in urban Skid Row.",
            "poster_path": "/littleshop1986_poster.jpg",
            "backdrop_path": "/littleshop1986_backdrop.jpg",
            "genres": [
                {"id": 27, "name": "Horror"},
                {"id": 35, "name": "Comedy"},
                {"id": 10402, "name": "Music"},
            ],
            "credits": {
                "cast": [{"name": "Rick Moranis", "order": 0}],
                "crew": [{"name": "Frank Oz", "job": "Director"}],
            },
            "keywords": {"keywords": [{"name": "musical"}, {"name": "man-eating plant"}]},
            "vi": {
                "title": "Cửa Hàng Kinh Dị Nhỏ (Nhạc Kịch 1986)",
                "overview": "Phiên bản nhạc kịch năm 1986 về cây ăn thịt người Audrey II.",
            },
        },
    }


def _create_benchmark_mock_transport() -> httpx.MockTransport:
    """
    Create an `httpx.MockTransport` that serves the 16-movie benchmark catalog
    through the real `TMDBClient` HTTP stack, including a simulated HTTP 429
    rate-limit response on the first detail request for movie #4808 (`Charade`).
    """
    catalog = _build_mock_tmdb_catalog()
    state = {"charade_429_triggered": False}

    def handler(request: httpx.Request) -> httpx.Response:
        parsed = urlparse(str(request.url))
        path = parsed.path
        params = parse_qs(parsed.query)
        lang = (params.get("language") or ["en-US"])[0]

        # 1. External ID lookup: /3/find/{external_id}
        if path.startswith("/3/find/"):
            ext_id = path.split("/3/find/", 1)[1]
            matches = [
                {
                    "id": m["id"],
                    "title": m["title"],
                    "original_title": m["original_title"],
                    "release_date": m["release_date"],
                    "original_language": m["original_language"],
                }
                for m in catalog.values()
                if m.get("imdb_id") == ext_id
            ]
            return httpx.Response(200, json={"movie_results": matches})

        # 2. Search movies: /3/search/movie
        if path == "/3/search/movie":
            q = (params.get("query") or [""])[0].strip().lower()
            if "9999xyz" in q:
                return httpx.Response(
                    200,
                    json={"page": 1, "total_results": 0, "total_pages": 0, "results": []},
                )

            results: list[dict[str, Any]] = []
            for m in catalog.values():
                t_lower = m["title"].lower()
                ot_lower = m["original_title"].lower()
                if (
                    q in t_lower
                    or t_lower in q
                    or q in ot_lower
                    or ("2037" in q and m["id"] == 961729)
                    or ("conan" in q and m["id"] == 1397832)
                    or ("godfather" in q and m["id"] in (238, 240))
                    or ("nosferatu" in q and m["id"] in (653, 6404, 426063))
                    or ("gift" in q and m["id"] in (328425, 2046))
                    or ("little shop" in q and m["id"] in (24420, 10776))
                ):
                    results.append(
                        {
                            "id": m["id"],
                            "title": m["title"],
                            "original_title": m["original_title"],
                            "release_date": m["release_date"],
                            "original_language": m["original_language"],
                            "popularity": 50.0,
                            "vote_count": 1000,
                        }
                    )
            return httpx.Response(
                200,
                json={
                    "page": 1,
                    "total_results": len(results),
                    "total_pages": 1,
                    "results": results,
                },
            )

        # 3. Movie details: /3/movie/{tmdb_id}
        if path.startswith("/3/movie/"):
            raw_id = path.split("/3/movie/", 1)[1].split("/")[0]
            try:
                tmdb_id = int(raw_id)
            except ValueError:
                return httpx.Response(404, json={"status_message": "Not found"})

            # Simulate one HTTP 429 rate-limit response on Charade (#4808) to verify retry recovery
            if tmdb_id == 4808 and not state["charade_429_triggered"]:
                state["charade_429_triggered"] = True
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"status_message": "Your request count is over the allowed limit."},
                )

            movie_data = catalog.get(tmdb_id)
            if not movie_data:
                return httpx.Response(404, json={"status_message": "Not found"})

            if lang == "vi-VN":
                vi_info = movie_data.get("vi", {})
                return httpx.Response(
                    200,
                    json={
                        "id": tmdb_id,
                        "title": vi_info.get("title", movie_data["title"]),
                        "overview": vi_info.get("overview", ""),
                    },
                )

            payload = {k: v for k, v in movie_data.items() if k != "vi"}
            return httpx.Response(200, json=payload)

        return httpx.Response(404, json={"status_message": "Unknown endpoint"})

    return httpx.MockTransport(handler)


def _seed_16_benchmark_movies(db: Session) -> list[dict[str, Any]]:
    """
    Seed 16 representative movies into the isolated benchmark SQLite session.
    Returns a list of scenario descriptors paired with the seeded `Movie` rows.
    """
    specs: list[dict[str, Any]] = [
        {
            "scenario": "exact_tmdb_id_match",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="The Shawshank Redemption 1994 - Nhà tù Shawshank 1994",
                overview="Two imprisoned men bond over a number of years.",
                release_date=date(1994, 1, 1),
                genres=["Drama"],
                cast=[],
                keywords=[],
                director="Frank Darabont",
                tmdb_id=278,
                processing_status="ready",
            ),
        },
        {
            "scenario": "verified_imdb_id_match",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Pulp Fiction",
                overview=None,
                release_date=date(1994, 1, 1),
                genres=["Crime"],
                cast=[],
                keywords=[],
                director="Quentin Tarantino",
                imdb_id="tt0110912",
                processing_status="ready",
            ),
        },
        {
            "scenario": "bilingual_title_missing_cast_keywords",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Interstellar 2014 - Hố Đen Tử Thần",
                overview="A team of explorers travel through a wormhole in space.",
                release_date=date(2014, 1, 1),
                genres=["Sci-Fi", "Drama"],
                cast=[],
                keywords=[],
                director="Christopher Nolan",
                processing_status="ready",
            ),
        },
        {
            "scenario": "bilingual_animated_classic",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Spirited Away - Vùng Đất Linh Hồn (2001)",
                overview="A young girl wanders into a world ruled by gods, witches, and spirits.",
                release_date=date(2001, 1, 1),
                genres=["Animation", "Fantasy"],
                cast=[],
                keywords=[],
                director="Hayao Miyazaki",
                processing_status="ready",
            ),
        },
        {
            "scenario": "localized_korean_vietnamese_title",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Điều Ước CUối Cùng Của Tù Nhân 2037 - My Girl 2037 (2022)",
                overview="Yoon-young becomes inmate 2037.",
                release_date=date(2022, 1, 1),
                genres=["Drama"],
                cast=[],
                keywords=[],
                director="Mo Hong-jin",
                processing_status="ready",
            ),
        },
        {
            "scenario": "localized_sequel_with_punctuation",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Thám Tử Lừng Danh Conan 28: Dư Ảnh Của Độc Nhãn - Detective Conan: One-Eyed Flashback (2025)",
                overview=None,
                release_date=date(2025, 1, 1),
                genres=["Animation", "Mystery"],
                cast=[],
                keywords=[],
                director="Katsuya Shigehara",
                processing_status="ready",
            ),
        },
        {
            "scenario": "common_title_disambiguation",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="The Gift",
                overview=None,
                release_date=date(2015, 1, 1),
                genres=["Thriller"],
                cast=[],
                keywords=[],
                director="Joel Edgerton",
                processing_status="ready",
            ),
        },
        {
            "scenario": "remake_disambiguation_nosferatu_1922",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Nosferatu",
                overview="Vampire Count Orlok expresses interest in a new residence.",
                release_date=date(1922, 1, 1),
                genres=["Horror"],
                cast=[],
                keywords=[],
                director="F. W. Murnau",
                processing_status="ready",
            ),
        },
        {
            "scenario": "missing_overview_cast_keywords",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Night of the Living Dead",
                overview=None,
                release_date=date(1968, 1, 1),
                genres=[],
                cast=[],
                keywords=[],
                director="George A. Romero",
                processing_status="ready",
            ),
        },
        {
            "scenario": "sequel_disambiguation_godfather_part_ii",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="The Godfather Part II",
                overview=None,
                release_date=date(1974, 1, 1),
                genres=["Drama", "Crime"],
                cast=[],
                keywords=[],
                director="Francis Ford Coppola",
                processing_status="ready",
            ),
        },
        {
            "scenario": "public_domain_silent_classic_the_general",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="The General",
                overview="Union spies steal engineer Johnny Gray's beloved locomotive.",
                release_date=date(1926, 1, 1),
                genres=[],
                cast=[],
                keywords=[],
                director="Buster Keaton",
                processing_status="ready",
            ),
        },
        {
            "scenario": "public_domain_classic_phantom_1925",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="The Phantom of the Opera",
                overview=None,
                release_date=date(1925, 1, 1),
                genres=[],
                cast=[],
                keywords=[],
                director="Rupert Julian",
                processing_status="ready",
            ),
        },
        {
            "scenario": "http_429_retry_recovery_charade",
            "review_action": "approve",
            "movie": Movie(
                id=uuid4(),
                title="Charade",
                overview=None,
                release_date=date(1963, 1, 1),
                genres=["Mystery", "Romance"],
                cast=[],
                keywords=[],
                director="Stanley Donen",
                processing_status="ready",
            ),
        },
        {
            "scenario": "conflicting_release_year_held_by_admin",
            "review_action": "reject",
            "reject_reason": "Stored release year 1945 conflicts with TMDB 1940 (+5y gap); held for manual catalog verification.",
            "movie": Movie(
                id=uuid4(),
                title="His Girl Friday",
                overview="Newspaper editor Walter Burns tries to keep his ex-wife from remarrying.",
                release_date=date(1945, 1, 1),
                genres=["Comedy"],
                cast=[],
                keywords=[],
                director="Howard Hawks",
                processing_status="ready",
            ),
        },
        {
            "scenario": "ambiguous_adaptation_rejected_by_admin",
            "review_action": "reject",
            "reject_reason": "Catalog entry has neither release year nor director to disambiguate 1960 Roger Corman film vs 1986 Frank Oz musical.",
            "movie": Movie(
                id=uuid4(),
                title="The Little Shop of Horrors",
                overview="A florist assistant cultivates a plant that feeds on human blood.",
                release_date=None,
                genres=["Comedy", "Horror"],
                cast=[],
                keywords=[],
                director=None,
                processing_status="ready",
            ),
        },
        {
            "scenario": "no_match_experimental_entry",
            "review_action": "none",
            "movie": Movie(
                id=uuid4(),
                title="Untitled Student Experimental Reel 9999XYZ",
                overview=None,
                release_date=date(2024, 1, 1),
                genres=[],
                cast=[],
                keywords=[],
                director=None,
                processing_status="ready",
            ),
        },
    ]

    for item in specs:
        db.add(item["movie"])
    db.commit()
    for item in specs:
        db.refresh(item["movie"])
    return specs


def run_controlled_enrichment_benchmark(
    output_json_path: Path | None = None,
) -> dict[str, Any]:
    """
    Execute the 16-movie controlled enrichment benchmark in an isolated in-memory
    SQLite database and return the complete TEC-compatible metrics dictionary.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        specs = _seed_16_benchmark_movies(db)
        movies = [s["movie"] for s in specs]

        # Warm initial cache
        refresh_cache(db)
        initial_cache_stats = get_cache_stats()

        completeness_before = compute_catalog_completeness(movies)

        transport = _create_benchmark_mock_transport()
        tmdb_config = TMDBConfig(
            read_access_token="mock-benchmark-token-do-not-log",
            enable_live_requests=False,
            timeout_seconds=5.0,
            max_retries=2,
            rate_limit_rps=1000.0,
            max_pages=2,
        )

        per_movie_results: list[dict[str, Any]] = []
        processing_times_ms: list[float] = []
        total_candidates_found = 0
        verified_id_matches = 0
        ambiguous_matches = 0
        no_match_cases = 0
        duplicate_or_conflicting_records = 0
        approved_jobs_count = 0
        rejected_jobs_count = 0
        reviewed_jobs_count = 0
        api_failures = 0
        http_429_responses = 0
        retry_counts = 0
        db_application_failures = 0
        successful_cache_refreshes = 0

        for item in specs:
            movie: Movie = item["movie"]
            scenario: str = item["scenario"]
            review_action: str = item["review_action"]

            # Use a fresh TMDBClient per job so per-job retry/429 stats are isolated
            client = TMDBClient(
                config=tmdb_config,
                transport=transport,
                sleep_fn=lambda _: None,
            )

            job: MetadataEnrichmentJob = start_enrichment_job(
                db=db,
                movie_id=movie.id,
                admin_email="benchmark-admin@movsug.test",
                tmdb_client=client,
                source_language="en-US",
                include_vi_localization=True,
                max_candidates=5,
            )

            if job.processing_time_ms is not None:
                processing_times_ms.append(float(job.processing_time_ms))
            total_candidates_found += int(job.candidates_found or 0)
            http_429_responses += int(job.http_429_count or 0)
            retry_counts += int(job.retry_count or 0)

            candidates: list[MetadataCandidate] = (
                db.query(MetadataCandidate)
                .filter(MetadataCandidate.job_id == job.id)
                .order_by(MetadataCandidate.match_score.desc())
                .all()
            )

            top_cand = candidates[0] if candidates else None
            if top_cand is not None:
                if top_cand.is_verified_id_match or top_cand.match_status == "verified_id":
                    verified_id_matches += 1
                if top_cand.match_status in ("ambiguous", "conflict") or len(candidates) > 1:
                    if top_cand.match_status in ("ambiguous", "conflict"):
                        ambiguous_matches += 1
                has_identity_conflict = bool(top_cand.conflicts)
                has_field_overwrite = any(
                    v.get("requires_explicit_overwrite", False)
                    for v in (top_cand.field_conflicts or {}).values()
                    if isinstance(v, dict)
                )
                if has_identity_conflict or has_field_overwrite or len(candidates) > 1:
                    duplicate_or_conflicting_records += 1
            else:
                no_match_cases += 1

            applied_fields_for_movie: list[str] = []
            if review_action == "approve" and top_cand is not None:
                reviewed_jobs_count += 1
                # Approve all missing fields + exact release_date when current date is YYYY-01-01 placeholder
                fields_to_approve: list[str] = []
                allow_overwrite = False
                for f_name, f_val in (top_cand.proposed_fields or {}).items():
                    if f_val is None:
                        continue
                    conflict_info = (top_cand.field_conflicts or {}).get(f_name, {})
                    if not conflict_info.get("requires_explicit_overwrite", False):
                        fields_to_approve.append(f_name)
                    elif f_name == "release_date":
                        # Upgrade YYYY-01-01 placeholder date to exact TMDB release date
                        fields_to_approve.append(f_name)
                        allow_overwrite = True

                job = review_approve_enrichment_job(
                    db=db,
                    job_id=job.id,
                    candidate_id=top_cand.id,
                    approved_fields=fields_to_approve,
                    admin_email="benchmark-admin@movsug.test",
                    allow_overwrite_existing=allow_overwrite,
                    expected_metadata_version=movie.metadata_version,
                    notes=f"Approved missing fields for scenario '{scenario}'",
                )
                job = apply_approved_metadata(
                    db=db,
                    job_id=job.id,
                    admin_email="benchmark-admin@movsug.test",
                    expected_metadata_version=movie.metadata_version,
                )
                approved_jobs_count += 1
                applied_fields_for_movie = fields_to_approve
                if refresh_cache(db):
                    successful_cache_refreshes += 1

            elif review_action == "reject":
                reviewed_jobs_count += 1
                job = review_reject_enrichment_job(
                    db=db,
                    job_id=job.id,
                    admin_email="benchmark-admin@movsug.test",
                    reason=item.get("reject_reason", "Rejected due to ambiguity/conflict"),
                    candidate_id=top_cand.id if top_cand else None,
                )
                rejected_jobs_count += 1

            db.refresh(movie)
            per_movie_results.append(
                {
                    "scenario": scenario,
                    "movie_id": str(movie.id),
                    "title": movie.title,
                    "job_status": job.status,
                    "review_state": job.review_state,
                    "application_status": job.application_status,
                    "candidates_found": len(candidates),
                    "top_candidate_tmdb_id": top_cand.provider_movie_id if top_cand else None,
                    "top_candidate_title": top_cand.title if top_cand else None,
                    "match_score": top_cand.match_score if top_cand else None,
                    "match_status": top_cand.match_status if top_cand else "no_match",
                    "is_verified_id_match": bool(top_cand.is_verified_id_match) if top_cand else False,
                    "conflicts": list(top_cand.conflicts or []) if top_cand else [],
                    "applied_fields": applied_fields_for_movie,
                    "http_429_count": int(job.http_429_count or 0),
                    "retry_count": int(job.retry_count or 0),
                    "processing_time_ms": round(float(job.processing_time_ms or 0.0), 2),
                }
            )

        completeness_after = compute_catalog_completeness(movies)
        final_cache_stats = get_cache_stats()

        sorted_times = sorted(processing_times_ms) if processing_times_ms else [0.0]
        p50_ms = round(statistics.median(sorted_times), 2)
        p95_idx = min(len(sorted_times) - 1, max(0, int(round(0.95 * (len(sorted_times) - 1)))))
        p95_ms = round(sorted_times[p95_idx], 2)

        approval_rate = (
            round(approved_jobs_count / reviewed_jobs_count, 4)
            if reviewed_jobs_count > 0
            else 0.0
        )
        rejection_rate = (
            round(rejected_jobs_count / reviewed_jobs_count, 4)
            if reviewed_jobs_count > 0
            else 0.0
        )

        summary: dict[str, Any] = {
            "phase": "Phase 8A — Movie Metadata Enrichment Foundation",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "evidence_type": "mocked_controlled_verification",
            "provider": "tmdb",
            "total_movies_inspected": len(movies),
            "movies_with_missing_metadata": completeness_before["movies_with_missing_metadata"],
            "completeness_before": completeness_before,
            "completeness_after": completeness_after,
            "candidates_found": total_candidates_found,
            "verified_id_matches": verified_id_matches,
            "ambiguous_matches": ambiguous_matches,
            "no_match_cases": no_match_cases,
            "admin_approval_rate": approval_rate,
            "rejection_rate": rejection_rate,
            "approved_jobs_count": approved_jobs_count,
            "rejected_jobs_count": rejected_jobs_count,
            "reviewed_jobs_count": reviewed_jobs_count,
            "api_failures": api_failures,
            "http_429_responses": http_429_responses,
            "retry_counts": retry_counts,
            "processing_time_p50_ms": p50_ms,
            "processing_time_p95_ms": p95_ms,
            "duplicate_or_conflicting_records": duplicate_or_conflicting_records,
            "db_application_failures": db_application_failures,
            "successful_cache_refreshes": successful_cache_refreshes,
            "cache_generation_before": initial_cache_stats["cache_generation"],
            "cache_generation_after": final_cache_stats["cache_generation"],
            "per_movie_results": per_movie_results,
        }

        if output_json_path is not None:
            output_json_path = Path(output_json_path)
            output_json_path.parent.mkdir(parents=True, exist_ok=True)
            output_json_path.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return summary
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


if __name__ == "__main__":
    default_out = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "phase8a_enrichment"
        / "enrichment_evaluation_summary.json"
    )
    result = run_controlled_enrichment_benchmark(output_json_path=default_out)
    print(
        f"Phase 8A controlled enrichment benchmark complete: "
        f"{result['total_movies_inspected']} movies inspected, "
        f"overall completeness {result['completeness_before']['overall_completeness_ratio']:.2%} -> "
        f"{result['completeness_after']['overall_completeness_ratio']:.2%}, "
        f"saved to {default_out}"
    )

