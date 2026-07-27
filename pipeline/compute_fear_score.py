"""Compute per-film fear scores from emotion CSVs.

Default emotion model labels (j-hartmann/emotion-english-distilroberta-base):
anger, disgust, fear, joy, neutral, sadness, surprise.

Fear score (v1, matches legacy scraper intent):
  - Among reviews labeled `fear`, mean Score → average_fear_score
  - Bayesian-ish shrink by review volume:
      weighted = avg * n / (n + k)   where k = mean n across films (or --k)

Also reports fear_share = (# reviews labeled fear) / (# reviews).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.paths import (  # noqa: E402
    COVERAGE,
    FEAR_SCORES,
    SCRAPER_EMOTIONS_DIR,
    UNIVERSE_EN,
    ensure_data_dirs,
)


def _score_one_file(path: Path, emotion: str = "fear") -> dict | None:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if df.empty or "Emotion" not in df.columns or "Score" not in df.columns:
        return None

    n = len(df)
    fear = df[df["Emotion"].astype(str).str.lower() == emotion.lower()]
    n_fear = len(fear)
    avg = float(fear["Score"].mean()) if n_fear else float("nan")
    return {
        "imdb_id": path.stem.replace("emotions_", ""),
        "review_count": n,
        "fear_count": n_fear,
        "fear_share": (n_fear / n) if n else 0.0,
        "average_fear_score": avg,
    }


def compute_fear_scores(
    coverage_path: Path = COVERAGE,
    emotions_dir: Path = SCRAPER_EMOTIONS_DIR,
    universe_path: Path = UNIVERSE_EN,
    emotion: str = "fear",
    k: float | None = None,
    min_reviews: int = 1,
) -> pd.DataFrame:
    if not coverage_path.exists():
        raise FileNotFoundError(
            f"Coverage not found: {coverage_path}. "
            "Run inventory_coverage.py first."
        )
    if not emotions_dir.exists():
        raise FileNotFoundError(f"Emotions dir not found: {emotions_dir}")

    cov = pd.read_csv(coverage_path)
    eligible = cov[cov["has_emotions"]].copy()
    rows: list[dict] = []
    for imdb_id in tqdm(
        eligible["imdb_id"].dropna().astype(str),
        desc="Scoring emotions",
    ):
        path = emotions_dir / f"emotions_{imdb_id}.csv"
        if not path.exists():
            continue
        row = _score_one_file(path, emotion=emotion)
        if row and row["review_count"] >= min_reviews:
            rows.append(row)

    scores = pd.DataFrame(rows)
    if scores.empty:
        return scores

    if k is None:
        k = float(scores["review_count"].mean())
    scores["k_factor"] = k
    scores["fear_score"] = (
        scores["average_fear_score"]
        * scores["fear_count"]
        / (scores["fear_count"] + k)
    )

    # Prefer fear_count in the shrink (only fear-labeled reviews),
    # matching legacy Average_Score over fear rows + Review_Count from all.
    # Also expose legacy-compatible weighted using all reviews as n:
    scores["fear_score_legacy_n"] = (
        scores["average_fear_score"]
        * scores["review_count"]
        / (scores["review_count"] + k)
    )

    meta_cols = [
        "id",
        "imdb_id",
        "title",
        "year",
        "runtime",
        "vote_average",
        "genre_names",
    ]
    if universe_path.exists():
        u = pd.read_csv(universe_path)
        keep = [c for c in meta_cols if c in u.columns]
        scores = scores.merge(u[keep], on="imdb_id", how="left")

    scores = scores.sort_values("fear_score", ascending=False)
    return scores.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute fear scores.")
    parser.add_argument("--out", type=Path, default=FEAR_SCORES)
    parser.add_argument("--emotion", default="fear")
    parser.add_argument(
        "--k",
        type=float,
        default=None,
        help="Shrinkage k; default = mean review_count",
    )
    parser.add_argument("--min-reviews", type=int, default=5)
    args = parser.parse_args()

    ensure_data_dirs()
    scores = compute_fear_scores(
        emotion=args.emotion,
        k=args.k,
        min_reviews=args.min_reviews,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.out, index=False)

    print(f"Wrote {args.out} ({len(scores)} films)")
    if not scores.empty:
        print("Top 10 by fear_score:")
        cols = [
            c
            for c in [
                "title",
                "year",
                "fear_score",
                "fear_share",
                "fear_count",
                "review_count",
            ]
            if c in scores.columns
        ]
        print(scores.head(10)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
