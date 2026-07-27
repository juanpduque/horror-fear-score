"""Inventory review/emotion coverage for the EN universe.

Joins universe_en.csv to legacy IMDb scraper folders (reviews + emotions)
and writes coverage + gap CSVs. Does not copy the ~2GB review/emotion tree.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.paths import (  # noqa: E402
    COVERAGE,
    GAP_NEED_EMOTIONS,
    GAP_NEED_IMDB,
    GAP_NEED_REVIEWS,
    RAW_EMOTIONS_DIR,
    RAW_REVIEWS_DIR,
    SCRAPER_EMOTIONS_DIR,
    SCRAPER_FEAR_RANKING,
    SCRAPER_REVIEWS_DIR,
    UNIVERSE_EN,
    ensure_data_dirs,
)


def _ids_from_glob(folder: Path, prefix: str) -> set[str]:
    if not folder.exists():
        return set()
    ids: set[str] = set()
    for p in folder.glob(f"{prefix}*.csv"):
        stem = p.stem
        if stem.startswith(prefix):
            ids.add(stem[len(prefix) :])
    return ids


def inventory(
    universe_path: Path = UNIVERSE_EN,
    reviews_dir: Path = SCRAPER_REVIEWS_DIR,
    emotions_dir: Path = SCRAPER_EMOTIONS_DIR,
    legacy_ranking: Path = SCRAPER_FEAR_RANKING,
) -> pd.DataFrame:
    if not universe_path.exists():
        raise FileNotFoundError(
            f"Universe not found: {universe_path}. Run build_universe.py first."
        )

    u = pd.read_csv(universe_path)
    review_ids = _ids_from_glob(reviews_dir, "reviews_") | _ids_from_glob(
        RAW_REVIEWS_DIR, "reviews_"
    )
    emotion_ids = _ids_from_glob(emotions_dir, "emotions_") | _ids_from_glob(
        RAW_EMOTIONS_DIR, "emotions_"
    )

    legacy_fear: set[str] = set()
    if legacy_ranking.exists():
        rank = pd.read_csv(legacy_ranking)
        if "imdb_id" in rank.columns:
            legacy_fear = set(rank["imdb_id"].dropna().astype(str))

    out = u.copy()
    out["has_imdb_id"] = out["imdb_id"].notna()
    out["has_reviews"] = out["imdb_id"].isin(review_ids)
    out["has_emotions"] = out["imdb_id"].isin(emotion_ids)
    out["has_legacy_fear_score"] = out["imdb_id"].isin(legacy_fear)

    out["status"] = "ready_for_score"
    out.loc[~out["has_imdb_id"], "status"] = "need_imdb"
    out.loc[
        out["has_imdb_id"] & ~out["has_reviews"], "status"
    ] = "need_reviews"
    out.loc[
        out["has_imdb_id"]
        & out["has_reviews"]
        & ~out["has_emotions"],
        "status",
    ] = "need_emotions"

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inventory review/emotion coverage for EN universe."
    )
    parser.add_argument("--universe", type=Path, default=UNIVERSE_EN)
    parser.add_argument("--out", type=Path, default=COVERAGE)
    args = parser.parse_args()

    ensure_data_dirs()
    cov = inventory(universe_path=args.universe)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cov.to_csv(args.out, index=False)

    need_imdb = cov[cov["status"] == "need_imdb"]
    need_reviews = cov[cov["status"] == "need_reviews"]
    need_emotions = cov[cov["status"] == "need_emotions"]
    ready = cov[cov["status"] == "ready_for_score"]

    need_imdb.to_csv(GAP_NEED_IMDB, index=False)
    need_reviews.to_csv(GAP_NEED_REVIEWS, index=False)
    need_emotions.to_csv(GAP_NEED_EMOTIONS, index=False)

    print(f"Wrote {args.out}")
    print(f"  total:              {len(cov)}")
    print(f"  has_imdb_id:        {int(cov['has_imdb_id'].sum())}")
    print(f"  has_reviews:        {int(cov['has_reviews'].sum())}")
    print(f"  has_emotions:       {int(cov['has_emotions'].sum())}")
    print(f"  legacy fear score:  {int(cov['has_legacy_fear_score'].sum())}")
    print(f"  ready_for_score:    {len(ready)}")
    print(f"  gap need_imdb:      {len(need_imdb)} -> {GAP_NEED_IMDB}")
    print(f"  gap need_reviews:   {len(need_reviews)} -> {GAP_NEED_REVIEWS}")
    print(f"  gap need_emotions:  {len(need_emotions)} -> {GAP_NEED_EMOTIONS}")
    print(f"  reviews dir exists: {SCRAPER_REVIEWS_DIR.exists()}")
    print(f"  emotions dir exists:{SCRAPER_EMOTIONS_DIR.exists()}")


if __name__ == "__main__":
    main()
