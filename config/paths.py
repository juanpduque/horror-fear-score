"""Central paths for horror-fear-score pipelines."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(
    os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1])
).expanduser()

AOF_ROOT = Path(
    os.getenv(
        "AOF_ROOT",
        "/Users/juanpabloduque/Documents/anatomy-of-fear",
    )
).expanduser()

IMDB_SCRAPER_ROOT = Path(
    os.getenv(
        "IMDB_SCRAPER_ROOT",
        "/Volumes/Adata Bituan/MacAir M1 Documentos/Pulp Analytics/"
        "Repos/IMDb-Movie-Scraper",
    )
).expanduser()

# --- this repo ---
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GAPS_DIR = DATA_DIR / "gaps"
EXPORTS_DIR = DATA_DIR / "exports"

# --- AOF inputs ---
AOF_DATA = AOF_ROOT / "pipeline" / "data"
AOF_HORROR_MOVIES = AOF_DATA / "horror_movies.csv"
AOF_IMDB_IDS = AOF_DATA / "imdb_ids.csv"
AOF_EXCLUDED_ANIMATION = AOF_DATA / "excluded_animation.csv"
AOF_EXCLUDED_MUSIC = AOF_DATA / "excluded_music.csv"
AOF_EXCLUDED_NON_ENGLISH = AOF_DATA / "excluded_non_english.csv"

# --- legacy scraper (reuse if present) ---
SCRAPER_REVIEWS_DIR = (
    IMDB_SCRAPER_ROOT
    / "data"
    / "processed"
    / "reviews"
    / "horror_movies_backup"
)
SCRAPER_EMOTIONS_DIR = (
    IMDB_SCRAPER_ROOT / "data" / "processed" / "movie_emotions_backup"
)
SCRAPER_FEAR_RANKING = (
    IMDB_SCRAPER_ROOT
    / "data"
    / "results"
    / "balanced_scary_movies_analysis_backup.csv"
)

# --- outputs ---
UNIVERSE_EN = PROCESSED_DIR / "universe_en.csv"
COVERAGE = GAPS_DIR / "coverage_en.csv"
GAP_NEED_IMDB = GAPS_DIR / "gap_need_imdb.csv"
GAP_NEED_REVIEWS = GAPS_DIR / "gap_need_reviews.csv"
GAP_NEED_EMOTIONS = GAPS_DIR / "gap_need_emotions.csv"
FEAR_SCORES = EXPORTS_DIR / "fear_scores.csv"


def ensure_data_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, GAPS_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
