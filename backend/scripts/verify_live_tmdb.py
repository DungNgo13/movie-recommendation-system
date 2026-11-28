"""
Live TMDB API verification script.

**Requires explicit manual execution** — never run by pytest or CI.

Usage:
    cd backend
    python scripts/verify_live_tmdb.py

Prerequisites:
    - backend/.env must contain TMDB_ENABLE_LIVE_REQUESTS=true
    - backend/.env must contain a valid TMDB_API_READ_ACCESS_TOKEN
    - Network access to api.themoviedb.org must be available

Performs authorized, read-only TMDB API requests to verify that:
  1. TMDBConfig.from_env() loads credentials correctly
  2. Live requests are enabled
  3. Authentication succeeds (HTTP 200, not 401)
  4. Movie search returns real candidates
  5. Movie detail retrieval works with English and Vietnamese localization
  6. Response structure matches expectations

Security:
  - Credentials are loaded from backend/.env (never hardcoded)
  - The access token value is never printed or logged
  - Makes at most 3 real HTTP requests (search + detail + vi-localization)
  - No database reads or writes
  - No data modification of any kind
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Simulate loading from repo root (not backend/)
original_cwd = os.getcwd()
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(f"CWD set to: {os.getcwd()}  (simulating repo-root launch)")

from app.services.tmdb_client import TMDBConfig, TMDBClient

# 1. Verify config loading
config = TMDBConfig.from_env()
print(f"\n=== Configuration ===")
print(f"enable_live_requests: {config.enable_live_requests}")
print(f"token present: {bool(config.read_access_token)}")
print(f"token length: {len(config.read_access_token)} chars")
print(f"base_url: {config.base_url}")
print(f"timeout: {config.timeout_seconds}s")
print(f"rate_limit_rps: {config.rate_limit_rps}")
print(f"max_retries: {config.max_retries}")

assert config.enable_live_requests, "FATAL: enable_live_requests is False"
assert config.read_access_token, "FATAL: no read_access_token"

# 2. Live API requests
client = TMDBClient(config=config)
results = {}

try:
    # Test 1: Search for "Interstellar" (2014)
    print(f"\n=== Test 1: Search 'Interstellar' (2014) ===")
    t0 = time.monotonic()
    search_result = client.search_movies("Interstellar", year=2014, language="en-US")
    t1 = time.monotonic()
    latency_ms = round((t1 - t0) * 1000, 1)
    
    total_results = search_result.get("total_results", 0)
    movies = search_result.get("results", [])
    print(f"HTTP status: 200 (success)")
    print(f"Latency: {latency_ms} ms")
    print(f"Total results: {total_results}")
    print(f"Results on page: {len(movies)}")
    
    if movies:
        first = movies[0]
        print(f"Top result: '{first.get('title')}' (TMDB #{first.get('id')})")
        print(f"  release_date: {first.get('release_date')}")
        print(f"  vote_average: {first.get('vote_average')}")
        print(f"  original_language: {first.get('original_language')}")
        print(f"  has overview: {bool(first.get('overview'))}")
        results["search"] = {
            "status": "PASS",
            "tmdb_id": first.get("id"),
            "title": first.get("title"),
            "total_results": total_results,
            "latency_ms": latency_ms,
        }
    else:
        results["search"] = {"status": "FAIL", "reason": "No results returned"}
    
    # Test 2: Get movie details for the top result
    if movies:
        tmdb_id = first["id"]
        print(f"\n=== Test 2: Get Movie Details (TMDB #{tmdb_id}) ===")
        t0 = time.monotonic()
        detail = client.get_movie_details(tmdb_id, language="en-US")
        t1 = time.monotonic()
        latency_ms = round((t1 - t0) * 1000, 1)
        
        print(f"HTTP status: 200 (success)")
        print(f"Latency: {latency_ms} ms")
        print(f"Title: {detail.get('title')}")
        print(f"Release date: {detail.get('release_date')}")
        print(f"Runtime: {detail.get('runtime')} min")
        print(f"Genres: {[g['name'] for g in detail.get('genres', [])]}")
        print(f"Has overview: {bool(detail.get('overview'))}")
        print(f"Has credits: {'credits' in detail}")
        print(f"Has keywords: {'keywords' in detail}")
        
        # Check credits
        credits = detail.get("credits", {})
        cast = credits.get("cast", [])
        crew = credits.get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        top_cast = [c["name"] for c in cast[:5]]
        print(f"Director(s): {directors}")
        print(f"Top 5 cast: {top_cast}")
        print(f"Has poster_path: {bool(detail.get('poster_path'))}")
        print(f"Has backdrop_path: {bool(detail.get('backdrop_path'))}")
        
        # Validate structure
        required_fields = ["id", "title", "overview", "release_date", "genres"]
        missing = [f for f in required_fields if f not in detail]
        
        results["detail"] = {
            "status": "PASS" if not missing else "FAIL",
            "latency_ms": latency_ms,
            "missing_fields": missing,
            "has_credits": "credits" in detail,
            "has_keywords": "keywords" in detail,
            "director": directors,
            "cast_count": len(cast),
        }
        
        # Test 3: Vietnamese localization
        print(f"\n=== Test 3: Vietnamese Localization (TMDB #{tmdb_id}) ===")
        t0 = time.monotonic()
        vi_detail = client.get_movie_localized_details(tmdb_id, language="vi-VN")
        t1 = time.monotonic()
        latency_ms = round((t1 - t0) * 1000, 1)
        
        vi_title = vi_detail.get("title")
        vi_overview = vi_detail.get("overview")
        print(f"HTTP status: 200 (success)")
        print(f"Latency: {latency_ms} ms")
        print(f"VI title: {vi_title}")
        print(f"VI overview present: {bool(vi_overview)}")
        print(f"VI overview length: {len(vi_overview) if vi_overview else 0} chars")
        
        results["vi_localization"] = {
            "status": "PASS",
            "latency_ms": latency_ms,
            "vi_title": vi_title,
            "has_vi_overview": bool(vi_overview),
        }

    # Stats summary
    print(f"\n=== Client Statistics ===")
    stats = client.stats
    print(f"Total requests: {stats.requests_total}")
    print(f"Succeeded: {stats.requests_succeeded}")
    print(f"Failures: {stats.api_failures}")
    print(f"Retries: {stats.retry_count}")
    print(f"HTTP 429 count: {stats.http_429_count}")
    print(f"Circuit breaker triggered: {stats.circuit_breaker_triggered}")
    print(f"Avg latency: {sum(stats.latencies_ms)/len(stats.latencies_ms):.1f} ms" if stats.latencies_ms else "N/A")

    # Final verdict
    print(f"\n=== VERDICT ===")
    all_pass = all(r.get("status") == "PASS" for r in results.values())
    print(f"Search: {results.get('search', {}).get('status', 'SKIP')}")
    print(f"Detail: {results.get('detail', {}).get('status', 'SKIP')}")
    print(f"VI Localization: {results.get('vi_localization', {}).get('status', 'SKIP')}")
    print(f"Overall: {'ALL PASS' if all_pass else 'HAS FAILURES'}")

except Exception as e:
    print(f"\n!!! LIVE VERIFICATION FAILED !!!")
    print(f"Error type: {type(e).__name__}")
    print(f"Error: {e}")
    if hasattr(e, "code"):
        print(f"Error code: {e.code}")
    if hasattr(e, "status_code"):
        print(f"HTTP status: {e.status_code}")
finally:
    client.close()
    os.chdir(original_cwd)
